import unittest
from similarity import address_similarity

class TestAddressSimilarity(unittest.TestCase):
    
    def test_exact_match(self):
        """Test that identical addresses return 1.0"""
        self.assertEqual(address_similarity("123 Main St", "123 Main St"), 1.0)
        self.assertEqual(address_similarity("Paris, France", "Paris, France"), 1.0)

    def test_normalization(self):
        """Test case insensitivity and whitespace handling"""
        score = address_similarity("  123   Main   St  ", "123 main st")
        self.assertEqual(score, 1.0)

    def test_country_aliases(self):
        """Test that country aliases are handled correctly"""
        # "Deutschland" should match "Germany"
        score = address_similarity("Berlin, Deutschland", "Berlin, Germany")
        self.assertGreater(score, 0.9)

        # "NL" should match "Netherlands"
        score = address_similarity("Amsterdam, NL", "Amsterdam, Netherlands")
        self.assertGreater(score, 0.9)

    def test_country_mismatch_penalty(self):
        """Test that different countries result in a low score"""
        # Same city name, different country
        score = address_similarity("Paris, Texas, USA", "Paris, France")
        # Should be penalized heavily (0.1 factor)
        self.assertLess(score, 0.4)

    def test_smart_alias_handling(self):
        """Test that dangerous aliases don't cause false positives"""
        # "IN" is an alias for India, but "Lake Station, IN, USA" is clearly USA.
        # "India" vs "USA" -> Mismatch? No, "IN" should be ignored in favor of "USA".
        # But wait, if we compare "Lake Station, IN, USA" to "Some Place, India", it SHOULD be a mismatch.

        # Case 1: "IN" (Indiana) vs "India" - Should be low
        score = address_similarity("Lake Station, IN, USA", "Mumbai, India")
        self.assertLess(score, 0.4) 

        # Case 2: "Rio de Janeiro" - "de" is alias for Germany.
        # "Rio de Janeiro, Brazil" vs "Berlin, Germany" -> Mismatch
        score = address_similarity("Rio de Janeiro, Brazil", "Berlin, Germany")
        self.assertLess(score, 0.3)

    def test_number_mismatch(self):
        """Test that different house numbers reduce the score"""
        score = address_similarity("10 Main St", "20 Main St")
        # Should be penalized (0.5 factor)
        self.assertLess(score, 0.6)

    def test_poi_mismatch(self):
        """Test that POI keywords (Airport, Port) affect the score"""
        # "Shanghai" vs "Port of Shanghai" -> POI mismatch
        score = address_similarity("Shanghai, China", "Port of Shanghai, China")
        self.assertLess(score, 0.85) # Base score might be high due to substring, but penalized

    def test_reordered_tokens(self):
        """Test that word order doesn't kill the score"""
        score = address_similarity("Main St 123", "123 Main St")
        self.assertEqual(score, 1.0) # Token set ratio handles this

    def test_typos(self):
        """Test resilience to small typos"""
        score = address_similarity("Grodno, Belarus", "Hrodna, Belarus")
        self.assertGreater(score, 0.6)

    def test_unknown_handling(self):
        """Test that 'unknown' values are handled gracefully"""
        self.assertEqual(address_similarity("Unknown", "Unknown"), 1.0)
        self.assertEqual(address_similarity("Unknown", "Paris"), 0.1)
        self.assertEqual(address_similarity(None, "Paris"), 0.0)

if __name__ == '__main__':
    unittest.main()
