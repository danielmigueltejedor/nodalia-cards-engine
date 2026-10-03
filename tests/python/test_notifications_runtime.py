"""Run the real background manager against a small HA boundary, without sending messages."""
import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest

ROOT=Path(__file__).parents[2]/'custom_components'/'nodalia'; PACKAGE='nodalia_background_tests'
package=ModuleType(PACKAGE);package.__path__=[str(ROOT)];sys.modules[PACKAGE]=package

def load(name):
    spec=importlib.util.spec_from_file_location(f'{PACKAGE}.{name}',ROOT/f'{name}.py');module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module);return module

engine=load('notification_engine');load('const')
# Stub only the external HA imports. All policy, manager, persistence decisions and message building are real.
names=['homeassistant','homeassistant.core','homeassistant.helpers','homeassistant.helpers.event','homeassistant.util','homeassistant.util.dt']
saved={name:sys.modules.get(name) for name in names}
for name in names: sys.modules[name]=ModuleType(name)
sys.modules['homeassistant.core'].HomeAssistant=object;sys.modules['homeassistant.core'].Event=object
sys.modules['homeassistant.helpers.event'].async_track_state_change_event=lambda *_:lambda:None
sys.modules['homeassistant.helpers.event'].async_track_time_interval=lambda *_:lambda:None
sys.modules['homeassistant.util.dt'].utcnow=lambda:datetime.now(timezone.utc)
sys.modules['homeassistant.util.dt'].now=lambda:datetime.now(timezone.utc)
sys.modules['homeassistant.util'].dt=sys.modules['homeassistant.util.dt']
storage_module=ModuleType(f'{PACKAGE}.storage');storage_module.NodaliaStorage=object;sys.modules[storage_module.__name__]=storage_module
runtime=load('notifications')
for name,previous in saved.items():
    if previous is None: sys.modules.pop(name,None)
    else:sys.modules[name]=previous

class Storage:
    def __init__(self):self.rows={}
    def get(self,section,key,default=None):return deepcopy(self.rows.get(section,{}).get(key,default))
    def get_section(self,section):return deepcopy(self.rows.get(section,{}))
    def set_delayed(self,section,key,value):self.rows.setdefault(section,{})[key]=deepcopy(value)
    async def async_set(self,section,key,value):self.set_delayed(section,key,value)
    async def async_flush(self):pass

class Services:
    def __init__(self,row):self.row=row;self.calls=[];self.deferred=None;self.entered=asyncio.Event();self.fail=False
    def has_service(self,*_):return True
    async def async_call(self,domain,service,data,**kwargs):
        self.calls.append((domain,service,data,kwargs))
        if domain=='weather':
            self.entered.set()
            if self.deferred is not None:await self.deferred
            if self.fail:raise RuntimeError('forecast unavailable')
            return {'weather.home':{'forecast':[self.row]}}
        return None

class BackgroundTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.storage=Storage();self.row={'datetime':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),'condition':'rainy','precipitation_probability':80,'temperature':20}
        self.services=Services(self.row)
        self.hass=SimpleNamespace(states={'weather.home':SimpleNamespace(state='cloudy',attributes={'supported_features':2,'temperature':0,'temperature_unit':'°C','friendly_name':'Tiempo'},last_changed=datetime.now(timezone.utc))},services=self.services,config=SimpleNamespace(language='es'),async_create_task=asyncio.create_task)
        self.profile=engine.normalize_profile({'enabled':True,'template_version':3,'language':'es','notify':{'enabled':True,'entities':['notify.phone'],'min_severity':'warning'},'entities':{'weather':['weather.home']}})
        self.manager=runtime.NodaliaNotificationManager(self.hass,self.storage);self.manager._profiles={'home':self.profile};self.manager._started=True

    def sent(self):return [call for call in self.services.calls if call[0]=='notify']

    async def test_forecast_push_is_background_and_deduplicates_across_restart(self):
        await self.manager._async_forecast_tick();await self.manager._async_forecast_tick()
        self.assertEqual(len(self.sent()),1);self.assertIn('80%',self.sent()[0][2]['message']);self.assertNotIn('20°C',self.sent()[0][2]['message'])
        self.assertEqual(self.services.calls[0][2]['type'],'hourly');self.assertTrue(self.services.calls[0][3]['return_response'])
        second=runtime.NodaliaNotificationManager(self.hass,self.storage);second._profiles={'home':self.profile};second._started=True
        await second._async_forecast_tick();self.assertEqual(len(self.sent()),1)
        self.assertEqual(second.list_inbox('home')[0]['measurements']['temperature']['value'],0)

    async def test_snoozed_forecasts_do_not_push_and_resume_when_expired(self):
        identity=engine.evaluate_forecasts(self.profile,'weather.home',[self.row],self.hass.states['weather.home'].attributes,datetime.now(timezone.utc),language='es')[0]['id']
        self.storage.set_delayed('notification_runtime','snoozed',{'home':{identity:(datetime.now(timezone.utc)+timedelta(hours=2)).timestamp()}})
        await self.manager._async_forecast_tick();self.assertEqual(self.sent(),[])
        self.storage.set_delayed('notification_runtime','snoozed',{'home':{identity:0}})
        await self.manager._async_forecast_tick();self.assertEqual(len(self.sent()),1)

    async def test_forecast_failures_and_disabled_profiles_send_nothing(self):
        self.services.fail=True;await self.manager._async_forecast_tick();self.assertEqual(self.sent(),[])
        self.services.fail=False;self.profile['enabled']=False;await self.manager._async_forecast_tick();self.assertEqual(self.sent(),[])
        self.assertEqual(len(self.services.calls),1)

    async def test_stop_cancels_an_inflight_forecast_and_prevents_delivery(self):
        self.services.deferred=asyncio.get_running_loop().create_future()
        self.manager._queue_forecast_refresh();await self.services.entered.wait();task=self.manager._forecast_task
        await self.manager.async_stop();self.assertTrue(task.done());self.assertIsNone(self.manager._forecast_task);self.assertEqual(self.sent(),[])

    async def test_legacy_saved_probability_templates_keep_probability(self):
        self.profile['smart']={'rain':{'message':'Probabilidad {value}.'}}
        self.profile['template_version']=2
        await self.manager._async_forecast_tick();self.assertEqual(self.sent()[0][2]['message'],'Probabilidad 80%.')
