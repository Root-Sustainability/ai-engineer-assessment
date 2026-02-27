import difflib
import re

def _normalize(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'[^\w\s]', ' ', text)
    return " ".join(text.strip().lower().split())

def _token_set_ratio(a: str, b: str) -> float:
    """Calculate similarity based on token overlap."""
    tokens_a = set(a.split())
    tokens_b = set(b.split())
    
    if not tokens_a or not tokens_b:
        return 0.0
        
    intersection = tokens_a.intersection(tokens_b)
    
    # Modified Dice coefficient weighted towards containment
    dice = 2.0 * len(intersection) / (len(tokens_a) + len(tokens_b))
    
    min_len = min(len(tokens_a), len(tokens_b))
    max_len = max(len(tokens_a), len(tokens_b))
    
    if min_len > 0:
        overlap_ratio = len(intersection) / min_len
        len_ratio = min_len / max_len
        
        # Boost score if one string is significantly contained in the other
        if overlap_ratio > 0.8 and len_ratio > 0.3:
            return max(dice, 0.8 + (overlap_ratio - 0.8) * 0.5)
            
    return dice

def _is_unknown(text: str) -> bool:
    return text.strip().lower() in {'unknown', 'n/a', 'null', 'none', 'undefined'}

def baseline_similarity(a: str, b: str) -> float:
    a_norm = _normalize(a)
    b_norm = _normalize(b)
    if not a_norm or not b_norm:
        return 0.0
    return difflib.SequenceMatcher(None, a_norm, b_norm).ratio()

COUNTRY_MAP = {
    'deutschland': 'germany', 'duitsland': 'germany', 'allemagne': 'germany',
    'nederland': 'netherlands', 'holland': 'netherlands', 'the netherlands': 'netherlands', 'pays-bas': 'netherlands',
    'belgique': 'belgium', 'belgie': 'belgium',
    'sverige': 'sweden', 'zweden': 'sweden',
    'osterreich': 'austria',
    'schweiz': 'switzerland', 'suisse': 'switzerland',
    'italia': 'italy',
    'espana': 'spain',
    'polska': 'poland',
    'brasil': 'brazil',
    'united kingdom': 'uk', 'great britain': 'uk',
    'united states': 'usa', 'united states of america': 'usa',
    'prc': 'china',
    'ierland': 'ireland'
}

COUNTRY_ALIASES = {
    'de': 'germany', 'nl': 'netherlands', 'be': 'belgium', 'se': 'sweden', 
    'at': 'austria', 'ch': 'switzerland', 'it': 'italy', 'es': 'spain', 
    'pl': 'poland', 'br': 'brazil', 'gb': 'uk', 'us': 'usa', 'cn': 'china',
    'ru': 'russia', 'jp': 'japan', 'in': 'india', 'ir': 'ireland', 'kr': 'south korea'
}

# Aliases that are common words in other languages
DANGEROUS_ALIASES = {'de', 'it', 'us', 'in', 'at', 'be'}

STANDARD_COUNTRIES = set(COUNTRY_MAP.values()) | set(COUNTRY_ALIASES.values())

CITY_ALIASES = {
    'bangalore': 'bengaluru',
    'bombay': 'mumbai',
    'madras': 'chennai',
    'calcutta': 'kolkata',
    'saigon': 'ho chi minh city',
    'kyiv': 'kiev',
    'rangoon': 'yangon'
}

def _replace_countries(text: str) -> str:
    """Replace country aliases with standard names."""
    # Handle multi-word replacements
    sorted_keys = sorted(COUNTRY_MAP.keys(), key=len, reverse=True)
    for key in sorted_keys:
        if key in text:
            pattern = r'\b' + re.escape(key) + r'\b'
            text = re.sub(pattern, COUNTRY_MAP[key], text)
            
    # Handle single word aliases and city aliases
    words = text.split()
    new_words = []
    for w in words:
        if w in COUNTRY_ALIASES and w not in DANGEROUS_ALIASES:
            new_words.append(COUNTRY_ALIASES[w])
        elif w in CITY_ALIASES:
            new_words.append(CITY_ALIASES[w])
        else:
            new_words.append(w)
            
    return " ".join(new_words)

def _get_countries(text: str) -> set:
    """Identify countries in text using standard names and aliases."""
    found = set()
    
    # Look for standard names
    for country in STANDARD_COUNTRIES:
        if re.search(r'\b' + re.escape(country) + r'\b', text):
            found.add(country)
            
    explicit_countries = found.copy()
    
    # Look for aliases, filtering out dangerous ones if explicit matches exist
    for alias, country in COUNTRY_ALIASES.items():
        if re.search(r'\b' + re.escape(alias) + r'\b', text):
            if alias in DANGEROUS_ALIASES and explicit_countries and country not in explicit_countries:
                continue
            found.add(country)
            
    return found

def address_similarity(a: str, b: str) -> float:
    """Compute a similarity score between two addresses (0.0 to 1.0)."""
    if not a or not b:
        return 0.0
        
    if _is_unknown(a) or _is_unknown(b):
        return 1.0 if _is_unknown(a) and _is_unknown(b) else 0.1
    
    a_norm = _replace_countries(_normalize(a))
    b_norm = _replace_countries(_normalize(b))
    
    if not a_norm or not b_norm:
        return 0.0
        
    if a_norm == b_norm:
        return 1.0
        
    # Calculate base scores
    seq_score = difflib.SequenceMatcher(None, a_norm, b_norm).ratio()
    token_score = _token_set_ratio(a_norm, b_norm)
    
    substring_score = 0.0
    if a_norm in b_norm or b_norm in a_norm:
        len_ratio = min(len(a_norm), len(b_norm)) / max(len(a_norm), len(b_norm))
        if len_ratio > 0.3:
            substring_score = 0.8 * len_ratio 
        else:
            substring_score = 0.3 * len_ratio
            
    final_score = max(seq_score, token_score, substring_score)
    
    # Extract numbers for mismatch checks
    nums_a = set(re.findall(r'\d+', a))
    nums_b = set(re.findall(r'\d+', b))
    
    # Number mismatch penalty
    if nums_a and nums_b and nums_a.isdisjoint(nums_b):
        final_score *= 0.5
            
    # Country mismatch penalty
    countries_a = _get_countries(a_norm)
    countries_b = _get_countries(b_norm)
    
    if countries_a and countries_b and countries_a.isdisjoint(countries_b):
        final_score *= 0.1
    
    # POI mismatch penalty
    poi_keywords = {'port', 'airport', 'aeroport', 'flughafen', 'luchthaven', 'havn', 'hamn', 'porto', 'puerto', 'terminal'}
    a_tokens = set(a_norm.split())
    b_tokens = set(b_norm.split())
    
    has_poi_a = not a_tokens.isdisjoint(poi_keywords)
    has_poi_b = not b_tokens.isdisjoint(poi_keywords)
    
    if has_poi_a != has_poi_b:
        final_score *= 0.8
        
    # Strict number check (e.g. postcodes)
    if nums_a and nums_b:
        union_nums = len(nums_a | nums_b)
        if union_nums > 0:
            num_jaccard = len(nums_a & nums_b) / union_nums
            
            long_nums_a = {n for n in nums_a if len(n) >= 4}
            long_nums_b = {n for n in nums_b if len(n) >= 4}
            
            if long_nums_a and long_nums_b and long_nums_a.isdisjoint(long_nums_b):
                 final_score *= 0.5
            elif num_jaccard < 1.0:
                  if not (nums_a.issubset(nums_b) or nums_b.issubset(nums_a)):
                      final_score *= 0.9

    # Residual mismatch check
    if not (has_poi_a or has_poi_b):
        common_tokens = a_tokens.intersection(b_tokens)
        if common_tokens:
            rem_a_text_tokens = [t for t in a_norm.split() if t not in common_tokens and not t.isdigit()]
            rem_b_text_tokens = [t for t in b_norm.split() if t not in common_tokens and not t.isdigit()]
            
            if rem_a_text_tokens and rem_b_text_tokens:
                rem_a_str = " ".join(rem_a_text_tokens)
                rem_b_str = " ".join(rem_b_text_tokens)
                
                rem_sim = difflib.SequenceMatcher(None, rem_a_str, rem_b_str).ratio()
                
                if rem_sim < 0.4:
                    final_score *= 0.5
                elif rem_sim < 0.6:
                    final_score *= 0.8

    # General vs Specific penalty
    if len(a_tokens) > 0 and len(b_tokens) > 0:
        min_len = min(len(a_tokens), len(b_tokens))
        max_len = max(len(a_tokens), len(b_tokens))
        len_ratio = min_len / max_len
        
        if len_ratio <= 0.5:
            if a_tokens.issubset(b_tokens) or b_tokens.issubset(a_tokens):
                final_score *= 0.6

    return final_score
