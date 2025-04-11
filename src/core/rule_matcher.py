import fnmatch # For wildcard matching
import re
from urllib.parse import urlparse

class RuleMatcher:
    """Matches requested domains against the configured rules."""

    def __init__(self):
        self._exact_matches = {} # {domain_lower: proxy_id}
        # Store wildcards as tuples: (specificity_key, pattern_lower, proxy_id)
        # Specificity key could be length or number of parts. Higher is more specific.
        self._wildcard_rules = []

    def _get_specificity(self, pattern: str) -> int:
        """Calculate a specificity score (higher is more specific)."""
        # Simple: use length. Longer patterns are generally more specific.
        # Could also count dots or non-wildcard characters.
        return len(pattern)

    def update_rules(self, rules_config: dict):
        """Processes and stores rules for matching."""
        print("[Matcher] Updating rules...")
        self._exact_matches.clear()
        temp_wildcards = []

        for rule_id, rule_data in rules_config.items():
            domain = rule_data.get("domain")
            proxy_id = rule_data.get("proxy_id") # Can be None for Direct

            if not domain:
                continue

            domain_lower = domain.lower()

            # Treat simple domain as exact match for now
            # More complex: *.domain could match domain too, needs priority
            is_wildcard = "*" in domain_lower or "?" in domain_lower

            if is_wildcard:
                # Store with specificity for sorting later
                specificity = self._get_specificity(domain_lower)
                temp_wildcards.append((specificity, domain_lower, proxy_id))
            else:
                self._exact_matches[domain_lower] = proxy_id

        # Sort wildcards by specificity (descending) then alphabetically for consistency
        self._wildcard_rules = sorted(temp_wildcards, key=lambda x: (-x[0], x[1]))

        print(f"[Matcher] Loaded {len(self._exact_matches)} exact rules and {len(self._wildcard_rules)} wildcard rules.")
        # print(f"[Matcher] Sorted wildcards: {[r[1] for r in self._wildcard_rules]}") # Debug print


    def match(self, domain: str) -> tuple[str | None, str | None]:
        """
        Finds the best matching rule for a given domain.
        Checks:
          1. Exact match (sub.domain.com)
          2. Wildcard match (*.domain.com) matching the full domain
          3. Parent domain exact match (domain.com)
          4. Parent domain wildcard match (*.com)
        Returns (proxy_id, rule_id) or (None, None) if no match.
        """
        target_domain = domain.lower().strip()
        if not target_domain: return None, None
        print(f"[Matcher] Attempting match for: '{target_domain}'")

        parts = target_domain.split('.')
        # Iterate from the full domain down to the base domain (e.g., sub.domain.com -> domain.com)
        for i in range(len(parts) - 1):
            current_check_domain = ".".join(parts[i:])
            print(f"[Matcher] Checking segment: '{current_check_domain}'") # Debug print

            # 1. Exact match for the current segment (or full domain initially)
            if current_check_domain in self._exact_matches:
                proxy_id = self._exact_matches[current_check_domain]
                print(f"[Matcher] Found exact match: Rule '{proxy_id}' -> Proxy '{proxy_id}'")
                return proxy_id, proxy_id

            # 2. Wildcard match (*.domain.com) for the parent of the current segment
            # Example: If checking "domain.com", look for "*.com" wildcard rules.
            # Example: If checking "sub.domain.com", look for "*.domain.com" wildcard rules.
            if i < len(parts) - 2: # Ensure there's a parent domain part to check wildcard for
                 parent_suffix = ".".join(parts[i+1:])
                 for specificity, pattern, proxy_id in self._wildcard_rules:
                     if fnmatch.fnmatchcase(parent_suffix, pattern):
                         print(f"[Matcher] Found wildcard match (*.{parent_suffix}): Rule '{proxy_id}' -> Proxy '{proxy_id}'")
                         return proxy_id, proxy_id

        # If we reach here, no specific or parent domain rule matched.
        print(f"[Matcher] No specific or parent rule found for '{target_domain}'.")
        return None, None # No match found

    def rule_count(self) -> int:
        """Returns the total number of loaded rules."""
        wildcard_count = sum(len(rules) for rules in self._wildcard_rules)
        return len(self._exact_matches) + wildcard_count 