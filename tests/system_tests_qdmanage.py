#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License
#

import re, json, unittest, os
from time import sleep
from system_test import TestCase, Process, Qdrouterd, main_module, TIMEOUT, DIR, wait_port
from subprocess import PIPE, STDOUT
from qpid_dispatch_internal.compat import OrderedDict, dictify
from qpid_dispatch_internal.management.qdrouter import QdSchema
from proton import Url

DUMMY = "org.apache.qpid.dispatch.dummy"

class QdmanageTest(TestCase):
    """Test qdmanage tool output"""

    @staticmethod
    def ssl_file(name):
        return os.path.join(DIR, 'ssl_certs', name)

    @classmethod
    def setUpClass(cls):
        super(QdmanageTest, cls).setUpClass()
        cls.inter_router_port = cls.tester.get_port()
        config_1 = Qdrouterd.Config([
            ('router', {'mode': 'interior', 'id': 'R1'}),
            ('sslProfile', {'name': 'server-ssl',
                             'certDb': cls.ssl_file('ca-certificate.pem'),
                             'certFile': cls.ssl_file('server-certificate.pem'),
                             'keyFile': cls.ssl_file('server-private-key.pem'),
                             'password': 'server-password'}),
            ('listener', {'port': cls.tester.get_port()}),
            ('connector', {'role': 'inter-router', 'port': cls.inter_router_port}),
            ('address', {'name': 'test-address', 'prefix': 'abcd', 'distribution': 'multicast'}),
            ('linkRoute', {'name': 'test-link-route', 'prefix': 'xyz', 'dir': 'in'}),
            ('autoLink', {'name': 'test-auto-link', 'addr': 'mnop', 'dir': 'out'}),
            ('listener', {'port': cls.tester.get_port(), 'sslProfile': 'server-ssl'})
        ])

        config_2 = Qdrouterd.Config([
            ('router', {'mode': 'interior', 'id': 'R2'}),
            ('listener', {'role': 'inter-router', 'port': cls.inter_router_port}),
        ])
        cls.router_2 = cls.tester.qdrouterd('test_router_2', config_2, wait=True)
        cls.router_1 = cls.tester.qdrouterd('test_router_1', config_1, wait=True)

    def address(self):
        return self.router_1.addresses[0]

    def run_qdmanage(self, cmd, input=None, expect=Process.EXIT_OK, address=None):
        p = self.popen(
            ['qdmanage'] + cmd.split(' ') + ['--bus', address or self.address(), '--indent=-1', '--timeout', str(TIMEOUT)],
            stdin=PIPE, stdout=PIPE, stderr=STDOUT, expect=expect)
        out = p.communicate(input)[0]
        try:
            p.teardown()
        except Exception, e:
            raise Exception("%s\n%s" % (e, out))
        return out

    def assert_entity_equal(self, expect, actual, copy=None):
        """Copy keys in copy from actual to idenity, then assert maps equal."""
        if copy:
            for k in copy: expect[k] = actual[k]
        self.assertEqual(expect, actual)

    def assert_entities_equal(self, expect, actual, copy=None):
        """Do assert_entities_equal on a list of maps."""
        for e, a in zip(expect, actual): self.assert_entity_equal(e, a, copy)

    def test_crud(self):

        def check(cmd, expect, copy=None, **kwargs):
            actual = json.loads(self.run_qdmanage(cmd))
            self.assert_entity_equal(expect, actual, copy=copy)

        expect = {'arg1': 'foo', 'type': DUMMY, 'name': 'mydummy2'}
        # create with type, name in attributes
        check('create arg1=foo type=dummy name=mydummy2', expect, copy=['identity'], attributes=json.dumps(expect))
        # create with type, name as arguments
        expect['name'] = 'mydummy'
        check('create name=mydummy type=dummy arg1=foo', expect, copy=['identity'])
        check('read --name mydummy', expect)
        check('read --identity %s' % expect['identity'], expect)
        expect.update([], arg1='bar', num1=555)
        check('update name=mydummy arg1=bar num1=555', expect)
        check('read --name=mydummy', expect)
        expect.update([], arg1='xxx', num1=888)
        # name outside attributes
        check('update name=mydummy arg1=xxx num1=888', expect)
        check('read --name=mydummy', expect)
        self.run_qdmanage('delete --name mydummy')
        self.run_qdmanage('read --name=mydummy', expect=Process.EXIT_FAIL)

    def test_stdin(self):
        """Test piping from stdin"""
        def check(cmd, expect, input, copy=None):
            actual = json.loads(self.run_qdmanage(cmd + " --stdin", input=input))
            self.assert_entity_equal(expect, actual, copy=copy)

        def check_list(cmd, expect_list, input, copy=None):
            actual = json.loads(self.run_qdmanage(cmd + " --stdin", input=input))
            self.assert_entities_equal(expect_list, actual, copy=copy)

        expect = {'type': DUMMY, 'name': 'mydummyx', 'arg1': 'foo'}
        check('create', expect, json.dumps(expect), copy=['identity'])

        expect_list = [{'type': DUMMY, 'name': 'mydummyx%s' % i} for i in xrange(3)]
        check_list('create', expect_list, json.dumps(expect_list), copy=['identity'])

        expect['arg1'] = 'bar'
        expect['num1'] = 42
        check('update', expect, json.dumps(expect))

        for i in xrange(3):
            expect_list[i]['arg1'] = 'bar'
            expect_list[i]['num1'] = i
        check_list('update', expect_list, json.dumps(expect_list))

    def test_query(self):

        def long_type(name):
            return u'org.apache.qpid.dispatch.'+name

        types = ['listener', 'log', 'container', 'router']
        long_types = [long_type(name) for name in types]

        qall = json.loads(self.run_qdmanage('query'))
        qall_types = set([e['type'] for e in qall])
        for t in long_types:
            self.assertIn(t, qall_types)

        qlistener = json.loads(self.run_qdmanage('query --type=listener'))
        self.assertEqual([long_type('listener')]*2, [e['type'] for e in qlistener])
        self.assertEqual(self.router_1.ports[0], int(qlistener[0]['port']))

        qattr = json.loads(
            self.run_qdmanage('query type name'))

        for e in qattr:
            self.assertEqual(2, len(e))

        def name_type(entities):
            ignore_types = [long_type(t) for t in ['router.link', 'connection', 'router.address']]
            return set((e['name'], e['type']) for e in entities
                       if e['type'] not in ignore_types)
        self.assertEqual(name_type(qall), name_type(qattr))

    def test_get_schema(self):
        schema = dictify(QdSchema().dump())
        actual = self.run_qdmanage("get-json-schema")
        self.assertEquals(schema, dictify(json.loads(actual)))
        actual = self.run_qdmanage("get-schema")
        self.assertEquals(schema, dictify(json.loads(actual)))

    def test_get_annotations(self):
        """
        The qdmanage GET-ANNOTATIONS call must return an empty dict since we don't support annotations at the moment.
        """
        out = json.loads(self.run_qdmanage("get-annotations"))
        self.assertTrue(len(out) == 0)

    def test_get_types(self):
        out = json.loads(self.run_qdmanage("get-types"))
        self.assertEqual(len(out), 28)

    def test_get_log(self):
        log = json.loads(self.run_qdmanage("get-log limit=1"))[0]
        self.assertEquals(['AGENT', 'trace'], log[0:2])
        self.assertRegexpMatches(log[2], 'get-log')

    def test_get_logstats(self):
        query_command = 'QUERY --type=logStats'
        logs = json.loads(self.run_qdmanage(query_command))
        # Each value returned by the above query should be
        # a log, and each log should contain an entry for each
        # log level.
        log_levels = [ 'criticalCount',
                       'debugCount',
                       'errorCount',
                       'infoCount',
                       'noticeCount',
                       'traceCount',
                       'warningCount'
                     ]
        n_log_levels = len ( log_levels )

        good_logs = 0

        for log_dict in logs:
            log_levels_present = 0
            log_levels_missing = 0
            for log_level in log_levels:
                if log_level in log_dict:
                    log_levels_present += 1
                else:
                    log_levels_missing += 1
            
            if log_levels_present == n_log_levels:
                good_logs += 1

        self.assertEquals ( good_logs, len(logs) )

    def test_ssl(self):
        """Simple test for SSL connection. Note system_tests_qdstat has a more complete SSL test"""
        url = Url(self.router_1.addresses[1], scheme="amqps")
        schema = dictify(QdSchema().dump())
        actual = self.run_qdmanage("GET-JSON-SCHEMA")
        self.assertEquals(schema, dictify(json.loads(actual)))

    def test_update(self):
        exception = False
        try:
            # Try to not set 'output'
            json.loads(self.run_qdmanage("UPDATE --type org.apache.qpid.dispatch.log --name log/DEFAULT output="))
        except Exception as e:
            exception = True
            self.assertTrue("InternalServerErrorStatus: CError: Configuration: Failed to open log file ''" in e.message)
        self.assertTrue(exception)

        # Set a valid 'output'
        output = json.loads(self.run_qdmanage("UPDATE --type org.apache.qpid.dispatch.log --name log/DEFAULT "
                                              "enable=trace+ output=A.log"))
        self.assertEqual("A.log", output['output'])
        self.assertEqual("trace+", output['enable'])

    def create(self, type, name, port):
        create_command = 'CREATE --type=' + type + ' --name=' + name + ' host=0.0.0.0 port=' + port
        connector = json.loads(self.run_qdmanage(create_command))
        return connector

    def test_check_address_name(self):
        long_type = 'org.apache.qpid.dispatch.router.config.address'
        query_command = 'QUERY --type=' + long_type
        output = json.loads(self.run_qdmanage(query_command))
        self.assertEqual(output[0]['name'], "test-address")
        self.assertEqual(output[0]['distribution'], "multicast")
        self.assertEqual(output[0]['prefix'], "abcd")

    def test_check_link_route_name(self):
        long_type = 'org.apache.qpid.dispatch.router.config.linkRoute'
        query_command = 'QUERY --type=' + long_type
        output = json.loads(self.run_qdmanage(query_command))
        self.assertEqual(output[0]['name'], "test-link-route")
        self.assertEqual(output[0]['dir'], "in")
        self.assertEqual(output[0]['prefix'], "xyz")

    def test_check_auto_link_name(self):
        long_type = 'org.apache.qpid.dispatch.router.config.autoLink'
        query_command = 'QUERY --type=' + long_type
        output = json.loads(self.run_qdmanage(query_command))
        self.assertEqual(output[0]['name'], "test-auto-link")
        self.assertEqual(output[0]['dir'], "out")
        self.assertEqual(output[0]['addr'], "mnop")

    def test_create_delete_connector(self):
        long_type = 'org.apache.qpid.dispatch.connector'
        query_command = 'QUERY --type=' + long_type
        output = json.loads(self.run_qdmanage(query_command))
        name = output[0]['name']

        # Delete an existing connector
        delete_command = 'DELETE --type=' + long_type + ' --name=' + name
        self.run_qdmanage(delete_command)
        output = json.loads(self.run_qdmanage(query_command))
        self.assertEqual(output, [])

        # Re-create the connector and then try wait_connectors
        self.create(long_type, name, str(QdmanageTest.inter_router_port))

        results = json.loads(self.run_qdmanage('QUERY --type=org.apache.qpid.dispatch.connection'))

        created = False
        for result in results:
            name = result['name']
            conn_name = 'connection/0.0.0.0:%s:' % QdmanageTest.inter_router_port
            if conn_name in name:
                created = True
        self.assertTrue(created)

    def test_zzz_add_connector(self):
        port = self.get_port()
        # dont provide role and make sure that role is defaulted to 'normal'
        command = "CREATE --type=connector --name=eaconn1 port=" + str(port) + " host=0.0.0.0"
        output = json.loads(self.run_qdmanage(command))
        self.assertEqual("normal", output['role'])

        exception = False
        try:
            port = self.get_port()
            # provide the same connector name (eaconn1) and make sure there is a duplicate value failure
            command = "CREATE --type=connector --name=eaconn1 port=" + str(port) + " host=0.0.0.0"
            output = json.loads(self.run_qdmanage(command))
        except Exception as e:
            self.assertTrue("Duplicate value 'eaconn1' for unique attribute 'name'" in e.message)
            exception = True

        self.assertTrue(exception)

        port = self.get_port()
        # provide role as 'normal' and make sure that it is preserved
        command = "CREATE --type=connector --name=eaconn2 port=" + str(port) + " host=0.0.0.0 role=normal"
        output = json.loads(self.run_qdmanage(command))
        self.assertEqual("normal", output['role'])

    def test_zzz_create_delete_listener(self):
        long_type = 'org.apache.qpid.dispatch.listener'
        name = 'ealistener'

        listener_port = self.get_port()

        listener = self.create(long_type, name, str(listener_port))
        self.assertEquals(listener['type'], long_type)
        self.assertEquals(listener['name'], name)

        exception_occurred = False

        try:
            # Try to connect to the port that was closed, it should not return an error
            wait_port(listener_port, timeout=2)
        except Exception as e:
            exception_occurred = True

        self.assertFalse(exception_occurred)

        delete_command = 'DELETE --type=' + long_type + ' --name=' + name
        self.run_qdmanage(delete_command)

        exception_occurred = False
        try:
            # Try deleting an already deleted connector, this should raise an exception
            self.run_qdmanage(delete_command)
        except Exception as e:
            exception_occurred = True
            self.assertTrue("NotFoundStatus: No entity with name='" + name + "'" in e.message)

        self.assertTrue(exception_occurred)

        try:
            # Try to connect to that port, it should not return an error
            wait_port(listener_port, timeout=2)
        except Exception as e:
            exception_occurred = True

        self.assertTrue(exception_occurred)

        # Now try the same thing with a short_type
        short_type = 'listener'

        listener_port = self.get_port()

        listener = self.create(long_type, name, str(listener_port))
        self.assertEquals(listener['type'], long_type)
        self.assertEquals(listener['name'], name)

        delete_command = 'DELETE --type=' + short_type + ' --name=' + name
        self.run_qdmanage(delete_command)

        exception_occurred = False

        try:
            # Try to connect to that port, it should not return an error
            wait_port(listener_port, timeout=2)
        except Exception as e:
            exception_occurred = True

        self.assertTrue(exception_occurred)

class QdmanageTestSsl(QdmanageTest):

    @classmethod
    def setUpClass(cls):
        super(QdmanageTestSsl, cls).setUpClass()

    def address(self):
        return self.router_1.addresses[1]

    def run_qdmanage(self, cmd, input=None, expect=Process.EXIT_OK, address=None):
        p = self.popen(
            ['qdmanage'] + cmd.split(' ') + ['--bus', address or self.address(),
                                             '--indent=-1',
                                             '--ssl-trustfile=' + self.ssl_file('ca-certificate.pem'),
                                             '--ssl-certificate=' + self.ssl_file('client-certificate.pem'),
                                             '--ssl-key=' + self.ssl_file('client-private-key.pem'),
                                             '--ssl-password=client-password',
                                             '--timeout', str(TIMEOUT),
                                             '--ssl-disable-peer-name-verify'],
            stdin=PIPE, stdout=PIPE, stderr=STDOUT, expect=expect)
        out = p.communicate(input)[0]
        try:
            p.teardown()
        except Exception, e:
            raise Exception("%s\n%s" % (e, out))
        return out

    def test_create_delete_connector(self):
        long_type = 'org.apache.qpid.dispatch.connector'
        query_command = 'QUERY --type=' + long_type
        output = json.loads(self.run_qdmanage(query_command))
        name = output[0]['name']

        # Delete an existing connector
        delete_command = 'DELETE --type=' + long_type + ' --name=' + name
        self.run_qdmanage(delete_command)
        output = json.loads(self.run_qdmanage(query_command))
        self.assertEqual(output, [])

        # Re-create the connector and then try wait_connectors
        self.create(long_type, name, str(QdmanageTestSsl.inter_router_port))

        results = json.loads(self.run_qdmanage('QUERY --type=org.apache.qpid.dispatch.connection'))

        created = False
        for result in results:
            name = result['name']
            conn_name = 'connection/0.0.0.0:%s:' % QdmanageTestSsl.inter_router_port
            if conn_name in name:
                created = True
        self.assertTrue(created)

    def test_create_delete_ssl_profile(self):
        long_type = 'org.apache.qpid.dispatch.sslProfile'
        ssl_profile_name = 'ssl-profile-test'
        ssl_create_command = 'CREATE --type=' + long_type + ' certFile=' + self.ssl_file('server-certificate.pem') + \
                         ' keyFile=' + self.ssl_file('server-private-key.pem') + ' password=server-password' + \
                         ' name=' + ssl_profile_name + ' certDb=' + self.ssl_file('ca-certificate.pem')

        output = json.loads(self.run_qdmanage(ssl_create_command))
        name = output['name']
        self.assertEqual(name, ssl_profile_name)

        long_type = 'org.apache.qpid.dispatch.listener'
        listener_name = 'sslListener'
        port = self.get_port()
        listener_create_command = 'CREATE --type=' + long_type + ' --name=sslListener host=127.0.0.1 port=' + str(port) + \
                                  ' saslMechanisms=EXTERNAL sslProfile=' + ssl_profile_name + \
                                  ' requireSsl=yes authenticatePeer=yes'
        output = json.loads(self.run_qdmanage(listener_create_command))
        name = output['name']
        self.assertEqual(name, listener_name)

        sleep(1)
        query_command = 'QUERY --type=listener'

        # Query on the port that was created by the preceding listener create
        output = json.loads(self.run_qdmanage(query_command, address="127.0.0.1:"+str(port)))

        ssl_listener_present = False

        for out in output:
            if out['name'] == 'sslListener':
                ssl_listener_present = True
                self.assertEqual(out['sslProfile'], 'ssl-profile-test')

        self.assertEqual(len(output), 3)
        self.assertTrue(ssl_listener_present)

        # Delete the SSL Profile. This will fail because there is a listener referencing the SSL profile.
        delete_command = 'DELETE --type=sslProfile --name=' + ssl_profile_name
        cannot_delete = False
        try:
            json.loads(self.run_qdmanage(delete_command))
        except Exception as e:
            cannot_delete = True
            self.assertTrue('ForbiddenStatus: SSL Profile is referenced by other listeners/connectors' in e.message)

        self.assertTrue(cannot_delete)

        # Deleting the listener first and then the SSL profile must work.
        delete_command = 'DELETE --type=listener --name=' + listener_name
        self.run_qdmanage(delete_command)

        delete_command = 'DELETE --type=sslProfile --name=' + ssl_profile_name
        self.run_qdmanage(delete_command)

    def test_zzz_router_query(self):
        long_type = 'org.apache.qpid.dispatch.router'
        query_command = 'QUERY --type=' + long_type
        output = json.loads(self.run_qdmanage(query_command))
        self.assertEqual(3, output[0]['connectionCount'])
        self.assertEqual(1, output[0]['linkRouteCount'])
        self.assertEqual(1, output[0]['autoLinkCount'])
        self.assertEqual('interior', output[0]['mode'])
        self.assertEqual('org.apache.qpid.dispatch.router', output[0]['type'])

if __name__ == '__main__':
    unittest.main(main_module())
