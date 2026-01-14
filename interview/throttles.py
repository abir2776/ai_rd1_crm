from rest_framework.throttling import SimpleRateThrottle

class CallRequestIPThrottle(SimpleRateThrottle):
    scope = "call_request_ip"

    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        return self.cache_format % {
            "scope": self.scope,
            "ident": ident,
        }
