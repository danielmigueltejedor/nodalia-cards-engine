"""Exercise the actual v3 handlers with an authenticated HA transport boundary."""
import asyncio
import importlib.util
import sys
from types import ModuleType, SimpleNamespace
import unittest
from test_capabilities import capabilities, Storage, Notifications, ROOT, PACKAGE

names=['voluptuous','homeassistant','homeassistant.auth','homeassistant.auth.permissions','homeassistant.auth.permissions.const','homeassistant.components','homeassistant.components.websocket_api']
saved={name:sys.modules.get(name) for name in names}
for name in names:sys.modules[name]=ModuleType(name)
vol=sys.modules['voluptuous'];vol.Required=lambda key,**_:key;vol.Optional=lambda key,**_:key
ws=sys.modules['homeassistant.components.websocket_api']
def command(schema):
    def decorate(func):func.schema=schema;return func
    return decorate
async def require_admin_call(func,hass,connection,msg):
    if not connection.user.is_admin:connection.send_error(msg['id'],'unauthorized','Admin required');return
    await func(hass,connection,msg)
def admin(func):
    async def wrapped(hass,connection,msg):await require_admin_call(func,hass,connection,msg)
    wrapped.schema=func.schema;return wrapped
ws.websocket_command=command;ws.async_response=lambda func:func;ws.require_admin=admin
sys.modules['homeassistant.components'].websocket_api=ws
permissions=sys.modules['homeassistant.auth.permissions.const'];permissions.POLICY_READ='read';permissions.POLICY_CONTROL='control'
spec=importlib.util.spec_from_file_location(f'{PACKAGE}.websocket_v3',ROOT/'websocket_v3.py');transport=importlib.util.module_from_spec(spec);spec.loader.exec_module(transport)
for name,previous in saved.items():
    if previous is None:sys.modules.pop(name,None)
    else:sys.modules[name]=previous

class Connection:
    def __init__(self,user='one',admin=False,allowed=True):
        self.permissions=[];self.results=[];self.errors=[]
        def check(entity,policy):self.permissions.append((entity,policy));return allowed
        self.user=SimpleNamespace(id=user,is_admin=admin,permissions=SimpleNamespace(check_entity=check))
    def send_result(self,message_id,result):self.results.append((message_id,result))
    def send_error(self,message_id,code,message):self.errors.append((message_id,code,message))

class TransportTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.storage=Storage();notifications=Notifications(self.storage)
        self.hass=SimpleNamespace(states={'vacuum.one':SimpleNamespace(state='docked',attributes={})},config=SimpleNamespace(time_zone='UTC',language='en'))
        self.hass.data={'nodalia':{'runtime':SimpleNamespace(started=True,capabilities=capabilities.NodaliaCapabilities(self.hass,self.storage,notifications))}}
        self.get={'id':1,'api_version':3,'entity_id':'vacuum.one'}

    async def test_nonadmin_cannot_preview_profiles_or_snooze_shared_alerts(self):
        connection=Connection()
        await transport.notifications_preview(self.hass,connection,{'id':1,'api_version':3,'profile':{},'profile_id':'home'})
        await transport.notifications_snooze(self.hass,connection,{'id':2,'api_version':3,'profile_id':'home','alert_id':'rain','until':'2030-01-01T00:00:00Z'})
        self.assertEqual([row[1] for row in connection.errors],['unauthorized','unauthorized']);self.assertEqual(self.storage.writes,[])

    async def test_entity_permissions_and_negotiated_generation_gate_sessions(self):
        denied=Connection(allowed=False);await transport.vacuum_get(self.hass,denied,self.get)
        self.assertEqual(denied.errors[0][1],'unauthorized');self.assertEqual(denied.permissions,[('vacuum.one','read')])
        old=Connection();await transport.vacuum_get(self.hass,old,{**self.get,'api_version':2})
        self.assertEqual(old.errors[0][1],'unsupported_api_version');self.assertEqual(old.permissions,[])

    async def test_session_owner_comes_from_the_connection_and_conflicts_are_returned(self):
        connection=Connection();msg={**self.get,'session':{'repeats':1},'expected_revision':0,'user_id':'other'}
        await transport.vacuum_set(self.hass,connection,msg);await transport.vacuum_set(self.hass,connection,msg)
        self.assertEqual(connection.results[0][1]['revision'],1);self.assertEqual(connection.errors[0][1],'conflict')
        self.assertEqual(connection.permissions,[('vacuum.one','control')]*2)
        second=Connection(user='other');await transport.vacuum_get(self.hass,second,self.get);self.assertIsNone(second.results[0][1]['session'])

    async def test_invalid_session_and_unloaded_runtime_do_not_write(self):
        connection=Connection();await transport.vacuum_set(self.hass,connection,{**self.get,'session':{'repeats':False},'expected_revision':0})
        self.assertEqual(connection.errors[0][1],'invalid_format');self.assertEqual(self.storage.writes,[])
        self.hass.data['nodalia']['runtime'].started=False
        await transport.vacuum_get(self.hass,connection,self.get);self.assertEqual(connection.errors[-1][1],'not_loaded')
