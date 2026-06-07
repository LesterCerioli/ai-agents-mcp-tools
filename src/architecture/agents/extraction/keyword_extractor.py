import re
from typing import Any


_USER_NOUN = r"users?|viewers?|students?|clients?|customers?|patients?|devices?|shoppers?|subscribers?|people|members?"

_SCALABILITY_PATTERNS: list[tuple[str, str | None, Any]] = [
    # "N million viewers / users / devices / ..."
    (
        rf"\b(\d[\d,\.]*)\s*(?:million|M)\s*(?:concurrent\s*)?(?:{_USER_NOUN})\b",
        "expected_users",
        lambda m: f"{m.group(1)} million",
    ),
    # "N thousand / Nk users / ..."
    (
        rf"\b(\d[\d,\.]*)\s*(?:thousand|k)\s*(?:{_USER_NOUN})\b",
        "expected_users",
        lambda m: f"{m.group(1)}k",
    ),
    # "N concurrent users / viewers / ..." or plain "N concurrent"
    (
        rf"\b(\d[\d,\.]*)\s*concurrent(?:\s*(?:{_USER_NOUN}))?\b",
        "peak_load",
        lambda m: f"{m.group(1)} concurrent",
    ),
    # "N rps / requests per second"
    (
        r"\b(\d[\d,\.]*)\s*(?:rps|requests?\s*/\s*second|requests?\s*per\s*second)\b",
        "peak_load",
        lambda m: f"{m.group(1)} rps",
    ),
    # General "50,000 students / 100,000 devices / ..."
    (
        rf"\b(\d[\d,\.]+)\s*(?:{_USER_NOUN})\b",
        "expected_users",
        lambda m: m.group(0).strip(),
    ),
    (r"\brapid\s*growth\b", "growth_rate", lambda _: "rapid"),
    (r"\bgrow(?:ing|th)\b", "growth_rate", lambda _: "growing"),
    (r"\bscal(?:e|ing|able)\b", None, None),
]

_AVAILABILITY_PATTERNS: list[tuple[str, str | None, Any]] = [
    (r"\b(99\.?\d*)\s*%\s*(?:uptime|availability|SLA)\b", "target_uptime", lambda m: f"{m.group(1)}%"),
    (r"\bhigh[- ]availability\b|\bHA\b", "target_uptime", lambda _: "high availability"),
    (r"\bfive\s*nines\b", "target_uptime", lambda _: "99.999%"),
    (r"\bRTO\s*(?:of\s*)?(\d+\s*(?:min(?:utes?)?|h(?:ours?)?|s(?:econds?)?))\b", "rto", lambda m: m.group(1)),
    (r"\bRPO\s*(?:of\s*)?(\d+\s*(?:min(?:utes?)?|h(?:ours?)?|s(?:econds?)?))\b", "rpo", lambda m: m.group(1)),
    (r"\bfault[- ]tolerant\b|\bresilient\b", None, None),
    (r"\bdisaster\s*recovery\b", None, None),
    (r"\bzero[- ]downtime\b", "target_uptime", lambda _: "99.99%+"),
]

_COMPLIANCE_FRAMEWORKS: dict[str, str] = {
    "GDPR": r"\bGDPR\b",
    "HIPAA": r"\bHIPAA\b",
    "SOC2": r"\bSOC\s*2\b",
    "PCI-DSS": r"\bPCI[- ]DSS\b|\bPCI\b",
    "ISO 27001": r"\bISO\s*27001\b",
    "CCPA": r"\bCCPA\b",
    "FERPA": r"\bFERPA\b",
    "LGPD": r"\bLGPD\b",
    "SOX": r"\bSOX\b|\bSarbanes[- ]Oxley\b",
}

_DOMAIN_PATTERNS: dict[str, list[str]] = {
    "e-commerce": [r"\be-?commerce\b", r"\bonline\s*store\b", r"\bmarketplace\b", r"\bshop(?:ping)?\b", r"\bproduct\s*catalog\b"],
    "fintech": [r"\bfintech\b", r"\bbanking\b", r"\bfinancial\b", r"\bpayments?\b", r"\blending\b", r"\binsur(?:ance|tech)\b", r"\binvestment\b"],
    "healthcare": [r"\bhealthcare\b", r"\bmedical\b", r"\bhospital\b", r"\bEHR\b", r"\bEMR\b", r"\btelemedicine\b", r"\bclinic\b", r"\bpatient\b", r"\bhealth\s*records?\b"],
    "saas": [r"\bSaaS\b", r"\bsoftware\s*as\s*a\s*service\b", r"\bsubscription\b", r"\bmulti[- ]tenant\b", r"\bB2B\b"],
    "iot": [r"\bIoT\b", r"\bInternet\s*of\s*Things\b", r"\bsensors?\b", r"\bdevices?\b", r"\bembedded\b", r"\btelemetry\b", r"\bfirmware\b"],
    "logistics": [r"\blogistics\b", r"\bsupply\s*chain\b", r"\bshipping\b", r"\bwarehouse\b", r"\bfleet\b", r"\bfleet\s*management\b"],
    "education": [r"\bedtech\b", r"\beducation\b", r"\blearning\b", r"\bLMS\b", r"\bcourses?\b", r"\bstudents?\b", r"\bteachers?\b", r"\bcurriculum\b"],
    "social": [r"\bsocial\s*network\b", r"\bcommunity\b", r"\bfeed\b", r"\buser[- ]generated\b", r"\bposts?\b", r"\bfollowers?\b"],
    "gaming": [r"\bgaming\b", r"\bgames?\b", r"\bmultiplayer\b", r"\bleaderboard\b", r"\bgame\s*engine\b"],
    "media": [r"\bmedia\b", r"\bstreaming\b", r"\bcontent\s*(?:delivery|platform)\b", r"\bvideo\b", r"\baudio\b", r"\bCDN\b"],
}

_INTEGRATION_SYSTEMS: dict[str, str] = {
    "Stripe": r"\bStripe\b",
    "PayPal": r"\bPayPal\b",
    "Braintree": r"\bBraintree\b",
    "Twilio": r"\bTwilio\b",
    "SendGrid": r"\bSendGrid\b",
    "AWS S3": r"\bS3\b|\bAWS\s*S3\b",
    "Firebase": r"\bFirebase\b",
    "Salesforce": r"\bSalesforce\b",
    "Slack": r"\bSlack\b",
    "Google Maps": r"\bGoogle\s*Maps?\b",
    "Auth0": r"\bAuth0\b",
    "Okta": r"\bOkta\b",
    "Kafka": r"\bKafka\b",
    "RabbitMQ": r"\bRabbitMQ\b",
    "Redis": r"\bRedis\b",
}

_INTEGRATION_PATTERN_KEYWORDS: dict[str, str] = {
    "REST": r"\bREST(?:ful)?\b|\bHTTP\s*API\b",
    "GraphQL": r"\bGraphQL\b",
    "gRPC": r"\bgRPC\b",
    "WebSocket": r"\bWebSocket(?:s)?\b|\bWS\b",
    "Event-driven": r"\bevent[- ]driven\b|\bevent\s*bus\b",
    "Webhook": r"\bwebhook(?:s)?\b",
    "Message Queue": r"\bmessage\s*queue\b|\bMQ\b",
}

_CLOUD_PROVIDERS: dict[str, str] = {
    "aws": r"\bAWS\b|\bAmazon\s*Web\s*Services?\b|\bEC2\b|\bLambda\b|\bEKS\b|\bS3\b",
    "gcp": r"\bGCP\b|\bGoogle\s*Cloud\b|\bGKE\b|\bFirestore\b|\bBigQuery\b",
    "azure": r"\bAzure\b|\bMicrosoft\s*Cloud\b|\bAKS\b",
}

_BUDGET_TIERS: dict[str, str] = {
    "startup": r"\bstartup\b|\bbootstrap(?:ped)?\b|\blean\b|\bmvp\b|\bpre[- ]seed\b|\bseed\s*stage\b",
    "mid-market": r"\bscale[- ]up\b|\bseries\s*[ab]\b|\bmid[- ]market\b|\bsmb\b",
    "enterprise": r"\benterprise\b|\blarge\s*(?:company|organization|corp)\b|\bfortune\s*500\b",
}

_COST_SENSITIVITY: dict[str, str] = {
    "high": r"\bcost[- ](?:effective|sensitive|conscious|efficient)\b|\bbudget[- ](?:friendly|constrained)\b|\bcheap\b|\blow[- ]cost\b",
    "low": r"\bpremium\b|\bno\s*budget\s*constraint\b|\benterprise[- ]grade\b",
    "medium": r"\breasonable\s*cost\b|\bmoderate\s*budget\b",
}

_TEAM_SIZE_PATTERNS: dict[str, list[str]] = {
    "1-5": [
        r"\bsolo\b", r"\bone\s*(?:person|developer|engineer)\b",
        r"\bsmall\s*team\b", r"\b[1-4]\s*devs?\b", r"\bfew\s*developers?\b",
    ],
    "5-20": [
        r"\b(?:5|6|7|8|9|10|15|20)\s*(?:developers?|engineers?|devs?)\b",
        r"\bteam\s*of\s*(?:5|6|7|8|9|10|15|20)\b",
    ],
    "20-100": [
        r"\b(?:2[0-9]|[3-9]\d)\s*(?:developers?|engineers?)\b",
        r"\blarge\s*(?:engineering\s*)?team\b",
    ],
    "100+": [
        r"\b1\d\d\+?\s*(?:developers?|engineers?)\b",
        r"\bhundreds?\s*of\s*(?:developers?|engineers?)\b",
    ],
}

_ORG_MATURITY: dict[str, str] = {
    "startup": r"\bstartup\b|\bbootstrap\b|\bmvp\b",
    "scale-up": r"\bscale[- ]up\b|\bgrowing\s*company\b|\bseries\s*[bc]\b",
    "enterprise": r"\benterprise\b|\blarge\s*(?:company|org(?:anization)?)\b|\bfortune\b",
}


def _matches_any(text: str, patterns: list[str]) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


class KeywordExtractor:
    """Extracts architecture requirement signals from text using rule-based pattern matching.

    SRP: responsible only for converting raw text into structured requirement dicts
    via keyword/regex matching. No confidence aggregation, no clarification logic.
    """

    def extract(self, text: str) -> dict[str, Any]:
        return {
            "scalability": self._extract_scalability(text),
            "availability": self._extract_availability(text),
            "compliance": self._extract_compliance(text),
            "domain_boundaries": self._extract_domain(text),
            "integration": self._extract_integration(text),
            "budget": self._extract_budget(text),
            "team_size": self._extract_team_size(text),
        }

    def _extract_scalability(self, text: str) -> dict[str, Any]:
        result: dict[str, Any] = {}

        for pattern, field_name, extractor in _SCALABILITY_PATTERNS:
            m = re.search(pattern, text, re.IGNORECASE)
            if m and field_name and extractor and field_name not in result:
                result[field_name] = extractor(m)

        has_signal = bool(result) or bool(re.search(r"\bscal(?:e|ing|able)\b", text, re.IGNORECASE))

        if result:
            result["status"] = "specified"
            result["confidence"] = 0.8
        elif has_signal:
            result["status"] = "ambiguous"
            result["confidence"] = 0.4
        else:
            result["status"] = "not_specified"
            result["confidence"] = 0.0

        return result

    def _extract_availability(self, text: str) -> dict[str, Any]:
        result: dict[str, Any] = {}

        for pattern, field_name, extractor in _AVAILABILITY_PATTERNS:
            m = re.search(pattern, text, re.IGNORECASE)
            if m and field_name and extractor and field_name not in result:
                result[field_name] = extractor(m)

        has_signal = bool(result) or bool(
            re.search(r"\bfault[- ]tolerant\b|\bresilient\b|\bdisaster\s*recovery\b", text, re.IGNORECASE)
        )

        if "target_uptime" in result:
            result["status"] = "specified"
            result["confidence"] = 0.85
        elif has_signal:
            result["status"] = "ambiguous"
            result["confidence"] = 0.5
        else:
            result["status"] = "not_specified"
            result["confidence"] = 0.0

        return result

    def _extract_compliance(self, text: str) -> dict[str, Any]:
        frameworks = [
            name for name, pattern in _COMPLIANCE_FRAMEWORKS.items()
            if re.search(pattern, text, re.IGNORECASE)
        ]
        has_generic = bool(
            re.search(r"\bcomplian(?:ce|t)\b|\bregulator[yi]\b|\baudit(?:able)?\b|\bcertified\b", text, re.IGNORECASE)
        )

        if frameworks:
            return {
                "status": "specified",
                "frameworks": frameworks,
                "audit_trail": True,
                "confidence": 0.9,
            }
        if has_generic:
            return {"status": "ambiguous", "frameworks": [], "confidence": 0.4}
        return {"status": "not_specified", "frameworks": [], "confidence": 0.0}

    def _extract_domain(self, text: str) -> dict[str, Any]:
        for domain, patterns in _DOMAIN_PATTERNS.items():
            if _matches_any(text, patterns):
                subdomains = [
                    d for d, pats in _DOMAIN_PATTERNS.items()
                    if d != domain and _matches_any(text, pats)
                ]
                return {
                    "status": "specified",
                    "primary_domain": domain,
                    "subdomains": subdomains,
                    "confidence": 0.85,
                }
        return {"status": "not_specified", "primary_domain": None, "subdomains": [], "confidence": 0.0}

    def _extract_integration(self, text: str) -> dict[str, Any]:
        systems = [
            name for name, pattern in _INTEGRATION_SYSTEMS.items()
            if re.search(pattern, text, re.IGNORECASE)
        ]
        patterns_found = [
            name for name, pattern in _INTEGRATION_PATTERN_KEYWORDS.items()
            if re.search(pattern, text, re.IGNORECASE)
        ]
        real_time = bool(re.search(r"\breal[- ]time\b|\bwebsockets?\b|\blive\s*(?:updates?|data)\b", text, re.IGNORECASE))

        if systems or patterns_found:
            return {
                "status": "specified",
                "external_systems": systems,
                "integration_patterns": patterns_found,
                "real_time": real_time if real_time else None,
                "confidence": 0.8 if systems else 0.6,
            }
        return {
            "status": "not_specified",
            "external_systems": [],
            "integration_patterns": [],
            "confidence": 0.0,
        }

    def _extract_budget(self, text: str) -> dict[str, Any]:
        tier = next(
            (t for t, p in _BUDGET_TIERS.items() if re.search(p, text, re.IGNORECASE)),
            None,
        )
        cloud = next(
            (c for c, p in _CLOUD_PROVIDERS.items() if re.search(p, text, re.IGNORECASE)),
            None,
        )
        cost = next(
            (s for s, p in _COST_SENSITIVITY.items() if re.search(p, text, re.IGNORECASE)),
            None,
        )

        if tier or cloud or cost:
            return {
                "status": "specified",
                "tier": tier,
                "cloud_preference": cloud,
                "cost_sensitivity": cost,
                "confidence": 0.75,
            }
        return {"status": "not_specified", "tier": None, "cloud_preference": None, "cost_sensitivity": None, "confidence": 0.0}

    def _extract_team_size(self, text: str) -> dict[str, Any]:
        size = next(
            (s for s, pats in _TEAM_SIZE_PATTERNS.items() if _matches_any(text, pats)),
            None,
        )
        maturity = next(
            (m for m, p in _ORG_MATURITY.items() if re.search(p, text, re.IGNORECASE)),
            None,
        )

        if size or maturity:
            return {
                "status": "specified",
                "engineering_team_size": size,
                "organizational_maturity": maturity,
                "confidence": 0.7,
            }
        return {"status": "not_specified", "engineering_team_size": None, "organizational_maturity": None, "confidence": 0.0}
