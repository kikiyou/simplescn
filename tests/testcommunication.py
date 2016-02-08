#! /usr/bin/env python3
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "simplescn"))

import unittest

class TestCom(unittest.TestCase):
    temptestdir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "temp_communication")
    def setUp(self):
        if os.path.isdir(self.temptestdir):
            shutil.rmtree(self.temptestdir)
        os.mkdir(self.temptestdir, 0o700)
        simplescn.pwcallmethodinst = lambda msg, requester: ""
        self.oldpwcallmethodinst = simplescn.pwcallmethodinst

    def tearDown(self):
        shutil.rmtree(self.temptestdir)
        simplescn.pwcallmethodinst = self.oldpwcallmethodinst
    
if __name__ == "main":
    unittest.main(verbosity=2)
