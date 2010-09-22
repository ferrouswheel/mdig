"""Unit test for DispersalFit.py"""

import DispersalFit
import unittest

def run_test():
    # run test by generating dispersal from known dist and trying to
    # recreate
    gamma = 500
    maxChange = 300
    s = generateSites(gamma)
    d = calcDistances(s)
    gguess = fitDispersal(d)
    print repr(gamma) + " fit= " + repr(gguess[0][0]) + "(" + \
        repr(gguess[1]) + ") , trun " \
        + repr(gguess[0][0]) + "(" + \
        repr(gguess[1]) + ")"
    g2=gguess
    for i in range(0,10):
        s2 = generateSites(g2[0][0])
        d2 = calcDistances(s2)
        g2 = fitDispersal(d2)
        print "fit= " + repr(g2[0][0]) + "(" + \
            repr(g2[1]) + ") , trun " \
            + repr(g2[0][0]) + "(" + \
            repr(g2[1]) + ")" 
        pdb.set_trace()

class DispersalFit(unittest.TestCase):                          
    startData = 1

    def testFromRomanKnownValues(self):                          
        """fromRoman should give known result with known input"""
        self.assertEqual(0, 0)                    

class DispersalFitErrors(unittest.TestCase):                            
    def testTooLarge(self):                                          
        """toRoman should fail with large input"""                   
        self.assertRaises(roman.OutOfRangeError, roman.toRoman, 4000)

class SanityCheck(unittest.TestCase):        
    def testSanity(self):                    
        """fromRoman(toRoman(n))==n for all n"""
        for integer in range(1, 4000):       
            numeral = roman.toRoman(integer) 
            result = roman.fromRoman(numeral)
            self.assertEqual(integer, result)

if __name__ == "__main__":
    unittest.main()  
