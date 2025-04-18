import fnmatch # For wildcard matching
import re
from urllib.parse import urlparse
import ipaddress # Import ipaddress

class RuleMatcher:
    """Matches requested domains or IP addresses against the configured rules."""

    def __init__(self):
        self._exact_domain_matches = {} # {domain_lower: proxy_id}
        self._exact_ip_matches = {}     # {ip_address_str: {None: proxy_id, port: proxy_id, ...}}
        # Store wildcards as tuples: (specificity_key, pattern_lower, proxy_id)
        # Specificity key could be length or number of parts. Higher is more specific.
        self._wildcard_domain_rules = []

    def _get_specificity(self, pattern: str) -> int:
        """Calculate a specificity score (higher is more specific)."""
        # Simple: use length. Longer patterns are generally more specific.
        # Could also count dots or non-wildcard characters.
        return len(pattern)

    def _is_ip_address(self, value: str) -> bool:
        """Checks if a string is a valid IP address."""
        try:
            ipaddress.ip_address(value)
            return True
        except ValueError:
            return False

    def update_rules(self, rules_config: dict):
        """Processes and stores rules for matching, separating IPs and domains, with port and port range support for IPs."""
        print("[Matcher] Updating rules...")
        self._exact_domain_matches.clear()
        self._exact_ip_matches.clear()  # Now {ip: {None: proxy_id, port: proxy_id, ...}}
        temp_wildcards = []

        for rule_id, rule_data in rules_config.items():
            target = rule_data.get("domain") # This field now holds domain or IP
            proxy_id = rule_data.get("proxy_id") # Can be None for Direct
            enabled = rule_data.get("enabled", True) # Process only enabled rules
            port = rule_data.get("port") if "port" in rule_data else None
            if port == "": port = None
            # Parse port or port range
            port_key = None
            if isinstance(port, str):
                if '-' in port:
                    try:
                        start, end = port.split('-', 1)
                        start = int(start)
                        end = int(end)
                        if 1 <= start <= 65535 and 1 <= end <= 65535 and start <= end:
                            port_key = (start, end)
                        else:
                            port_key = None
                    except Exception:
                        port_key = None
                else:
                    try:
                        port_key = int(port)
                    except Exception:
                        port_key = None
            elif isinstance(port, int):
                port_key = port
            else:
                port_key = None

            if not target or not enabled:
                continue

            target_lower = target.lower()

            # Differentiate between IP and Domain
            if self._is_ip_address(target_lower):
                # Store exact IP matches with port and range support
                if target_lower not in self._exact_ip_matches:
                    self._exact_ip_matches[target_lower] = {}
                self._exact_ip_matches[target_lower][port_key] = proxy_id
            else:
                # Process as domain (check for wildcards)
                is_wildcard = "*" in target_lower or "?" in target_lower
                if is_wildcard:
                    # Store domain wildcards with specificity
                    specificity = self._get_specificity(target_lower)
                    temp_wildcards.append((specificity, target_lower, proxy_id))
                else:
                    # Store exact domain matches
                    self._exact_domain_matches[target_lower] = proxy_id

        # Sort wildcards by specificity (descending) then alphabetically for consistency
        self._wildcard_domain_rules = sorted(temp_wildcards, key=lambda x: (-x[0], x[1]))

        print(f"[Matcher] Loaded {len(self._exact_domain_matches)} exact domains, "
              f"{len(self._exact_ip_matches)} exact IPs, "
              f"and {len(self._wildcard_domain_rules)} wildcard domain rules.")
        # print(f"[Matcher] Sorted wildcards: {[r[1] for r in self._wildcard_domain_rules]}") # Debug print

    def match(self, target: str, port: int = None) -> tuple[str | None, str | None]:
        """
        Finds the best matching rule for a given domain or IP address, with port and port range support for IPs.
        If target is an IP:
          1. Exact IP+port match
          2. IP+port in range match
          3. Exact IP match (all ports)
        If target is a Domain:
          1. Exact match (sub.domain.com)
          2. Wildcard match (*.domain.com) matching the full domain
          3. Parent domain exact match (domain.com)
          4. Parent domain wildcard match (*.com)

        Returns (proxy_id, rule_id) or (None, None) if no match.
        Note: Currently rule_id returned is the same as proxy_id for simplicity.
              A future enhancement could map back to the original rule_id if needed.
        """
        target_lower = target.lower().strip()
        if not target_lower: return None, None
        print(f"[Matcher] Attempting match for: '{target_lower}' (port={port})")

        # Check if the target is an IP address
        if self._is_ip_address(target_lower):
            ip_rules = self._exact_ip_matches.get(target_lower)
            if ip_rules:
                # 1. Try port-specific match
                if port is not None and port in ip_rules:
                    proxy_id = ip_rules[port]
                    print(f"[Matcher] Found exact IP+port match: {target_lower}:{port} -> Proxy '{proxy_id}'")
                    return proxy_id, proxy_id
                # 2. Try port range match
                if port is not None:
                    for key, proxy_id in ip_rules.items():
                        if isinstance(key, tuple) and key[0] <= port <= key[1]:
                            print(f"[Matcher] Found IP+port range match: {target_lower}:{port} in {key[0]}-{key[1]} -> Proxy '{proxy_id}'")
                            return proxy_id, proxy_id
                # 3. Try generic IP match (all ports)
                if None in ip_rules:
                    proxy_id = ip_rules[None]
                    print(f"[Matcher] Found exact IP match (all ports): {target_lower} -> Proxy '{proxy_id}'")
                    return proxy_id, proxy_id
                print(f"[Matcher] No specific IP rule found for '{target_lower}' (port={port}).")
                return None, None # No match for IP

        # If not IP, proceed with domain matching logic
        print(f"[Matcher] Target '{target_lower}' is a domain. Proceeding with domain matching...")
        parts = target_lower.split('.')
        # Iterate from the full domain down to the base domain
        for i in range(len(parts)):
            current_check_domain = ".".join(parts[i:])
            if not current_check_domain: continue

            print(f"[Matcher] Checking domain segment: '{current_check_domain}'")

            # 1. Exact domain match for the current segment
            if current_check_domain in self._exact_domain_matches:
                proxy_id = self._exact_domain_matches[current_check_domain]
                print(f"[Matcher] Found exact domain match: '{current_check_domain}' -> Proxy '{proxy_id}'")
                return proxy_id, proxy_id

            # 2. Wildcard domain match for the current segment
            best_wildcard_match = None
            best_specificity = -1

            for specificity, pattern, proxy_id in self._wildcard_domain_rules:
                if fnmatch.fnmatchcase(current_check_domain, pattern):
                    if specificity > best_specificity:
                         best_specificity = specificity
                         best_wildcard_match = (proxy_id, proxy_id)
                         print(f"[Matcher] Found potential wildcard match: '{current_check_domain}' vs '{pattern}' (Specificity: {specificity}) -> Proxy '{proxy_id}'")

            if best_wildcard_match:
                 print(f"[Matcher] Using best wildcard match: Proxy '{best_wildcard_match[0]}'")
                 return best_wildcard_match

        print(f"[Matcher] No domain rule found for '{target_lower}' or its parents.")
        return None, None # No match found

    def rule_count(self) -> int:
        """Returns the total number of loaded rules."""
        # Update count to include IPs
        return len(self._exact_domain_matches) + len(self._exact_ip_matches) + len(self._wildcard_domain_rules) 