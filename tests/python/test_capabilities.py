"""Exercise v3 operations with real policies and an in-memory HA boundary."""
import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest

ROOT = Path(__file__).parents[2] / 'custom_components' / 'nodalia'
PACKAGE = 'nodalia_capability_tests'
package = ModuleType(PACKAGE); package.__path__ = [str(ROOT)]; sys.modules[PACKAGE] = package

def load(name):
    spec = importlib.util.spec_from_file_location(f'{PACKAGE}.{name}', ROOT / f'{name}.py')
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module); return module

climate = load('climate_engine'); engine = load('notification_engine'); capabilities = load('capabilities')

class Storage:
    def __init__(self): self.rows = {}; self.writes = []
    def get(self, section, key, default=None): return deepcopy(self.rows.get(section, {}).get(key, default))
    def get_section(self, section): return deepcopy(self.rows.get(section, {}))
    async def async_set(self, section, key, value):
        await asyncio.sleep(0)
        self.rows.setdefault(section, {})[key] = deepcopy(value); self.writes.append((section,key))

class Notifications:
    def __init__(self, storage): self.storage = storage
    def _template_values(self, *_): return {}
    def _normalize_profile_id(self, value): return value.strip().lower()
    def get_profile(self, profile): return {} if profile == 'home' else None
    def dismissed(self, *_): return []
    def is_snoozed(self, profile, alert): return self.storage.get('notification_runtime','snoozed',{}).get(profile,{}).get(alert,0) > datetime.now(timezone.utc).timestamp()

class CapabilityTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.storage = Storage(); self.notifications = Notifications(self.storage)
        self.states = {'vacuum.one':SimpleNamespace(state='docked',attributes={}), 'climate.one':SimpleNamespace(state='heat',attributes={}), 'weather.home':SimpleNamespace(state='rainy',attributes={'temperature':0,'temperature_unit':'°C','precipitation_probability':80,'friendly_name':'Tiempo'})}
        self.hass = SimpleNamespace(states=self.states, config=SimpleNamespace(time_zone='Europe/Madrid',language='es'))
        self.api = capabilities.NodaliaCapabilities(self.hass,self.storage,self.notifications)

    def profile(self):
        return {'enabled':True,'template_version':3,'language':'es','notify':{'enabled':True,'entities':['notify.phone'],'min_severity':'info'},'entities':{'weather':['weather.home']},'smart':{'rain':{'message':'Probabilidad {value}; temperatura {temperature}{temperature_unit}.'}}}

    async def test_preview_is_side_effect_free_and_separates_rain_measurements(self):
        result = self.api.preview_notifications(self.profile(),'home')
        self.assertTrue(result['dry_run']); self.assertEqual(self.storage.writes,[])
        self.assertEqual(result['alerts'][0]['message'],'Probabilidad 80%; temperatura 0°C.')
        self.assertEqual(result['alerts'][0]['measurements']['temperature']['value'],0)
        self.assertTrue(result['alerts'][0]['delivery_eligible'])

    async def test_preview_reports_disabled_delivery_and_missing_entities(self):
        profile=self.profile(); profile['enabled']=False; profile['entities']['weather'].append('weather.missing')
        result=self.api.preview_notifications(profile,'home')
        self.assertEqual(result['alerts'][0]['blocked_reason'],'delivery_policy')
        self.assertEqual(result['missing_entities'],['weather.missing']); self.assertEqual(self.storage.writes,[])

    async def test_snooze_persists_and_expiry_is_validated(self):
        until=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()
        result=await self.api.snooze('HOME','rain:weather.home',until)
        self.assertEqual(result['profile_id'],'home'); self.assertTrue(self.notifications.is_snoozed('home','rain:weather.home'))
        self.assertEqual(self.api.preview_notifications(self.profile(),'home')['alerts'][0]['blocked_reason'],'snoozed')
        for invalid in ('bad','2026-01-01T00:00:00','2020-01-01T00:00:00Z',(datetime.now(timezone.utc)+timedelta(days=8)).isoformat()):
            with self.assertRaises(ValueError): await self.api.snooze('home','rain',invalid)
        with self.assertRaises(ValueError): await self.api.snooze('absent','rain',until)

    async def test_sessions_are_private_defensive_and_compare_revisions_atomically(self):
        self.assertEqual(self.api.get_session('one','vacuum.one')['revision'],0)
        responses=await asyncio.gather(*(self.api.set_session('one','vacuum.one',{'repeats':1},0) for _ in range(2)),return_exceptions=True)
        self.assertEqual(sum(isinstance(value,capabilities.RevisionConflict) for value in responses),1)
        self.assertEqual(self.api.get_session('two','vacuum.one')['session'],None)
        saved=self.api.get_session('one','vacuum.one'); saved['session']['repeats']=9
        self.assertEqual(self.api.get_session('one','vacuum.one')['session']['repeats'],1)
        with self.assertRaises(ValueError): await self.api.set_session('one','climate.one',{},0)

    async def test_invalid_selections_and_payloads_never_write(self):
        for session in ({'repeats':True},{'repeats':0},{'manualZones':[{'x1':0,'y1':0,'x2':0,'y2':1}]},{'manualZones':[{'x1':0,'y1':0,'x2':float('nan'),'y2':1}]},{'activeMode':'execute'},{'selectedRoomIds':['x'*129]},{'unused':'x'*17000}):
            with self.assertRaises(ValueError): await self.api.set_session('one','vacuum.one',session,0)
        self.assertEqual(self.storage.writes,[])

    async def test_climate_preview_uses_ha_timezone_without_saving_or_running_devices(self):
        schedule={'enabled':True,'slots':[{'day':'sun','start':'01:00','end':'09:00','temperature':21}]}
        result=self.api.preview_climate('climate.one',schedule,'2026-10-04T05:00:00Z')
        self.assertEqual(result['effective_slot']['temperature'],21)
        self.assertEqual(result['at'],'2026-10-04T07:00:00+02:00'); self.assertTrue(result['dry_run']); self.assertEqual(self.storage.writes,[])
        with self.assertRaises(ValueError): self.api.preview_climate('climate.one',schedule,'2026-10-04T05:00:00')

    async def test_forecast_evaluation_uses_upcoming_probability_not_future_temperature(self):
        now=datetime(2026,10,3,10,tzinfo=timezone.utc)
        rows=[{'datetime':(now+timedelta(hours=2)).isoformat(),'condition':'rainy','precipitation_probability':90,'temperature':18},{'datetime':(now-timedelta(hours=1)).isoformat(),'condition':'rainy','precipitation_probability':99},{'datetime':(now+timedelta(hours=1)).isoformat(),'condition':'rainy','precipitation_probability':80,'temperature':12},None,{'datetime':'broken'}]
        alerts=engine.evaluate_forecasts(engine.normalize_profile(self.profile()),'weather.home',rows,self.states['weather.home'].attributes,now,language='es')
        self.assertEqual(alerts[0]['message'],'Probabilidad 80%; temperatura 0°C.')
        self.assertIn('forecast:',alerts[0]['id']); self.assertEqual(alerts[0]['forecast_at'],rows[2]['datetime'])

    async def test_missing_probability_and_zero_temperature_are_not_invented(self):
        now=datetime.now(timezone.utc); row={'datetime':(now+timedelta(hours=1)).isoformat(),'condition':'rainy'}
        profile=self.profile();profile['smart']={}
        alert=engine.evaluate_forecasts(engine.normalize_profile(profile),'weather.home',[row],{},now,language='es')[0]
        self.assertNotIn('%',alert['message']);self.assertEqual(alert['measurements']['temperature'],{'value':None,'unit':''})
        row['precipitation_probability']=0
        alert=engine.evaluate_forecasts(engine.normalize_profile(profile),'weather.home',[row],self.states['weather.home'].attributes,now,language='es')[0]
        self.assertIn('0%',alert['message']);self.assertEqual(alert['measurements']['temperature']['value'],0)

    async def test_forecast_obeys_minimum_severity_and_rejects_invalid_probabilities(self):
        now=datetime.now(timezone.utc); row={'datetime':(now+timedelta(hours=1)).isoformat(),'condition':'rainy','precipitation_probability':80}
        profile=self.profile(); profile['notify']['min_severity']='critical'
        self.assertEqual(engine.evaluate_forecasts(engine.normalize_profile(profile),'weather.home',[row],{},now),[])
        for invalid in (-1,101,float('nan'),float('inf'),'bad'):
            self.assertIsNone(engine.rain_probability({'precipitation_probability':invalid}))
