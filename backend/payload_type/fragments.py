class PayloadTypeFragments:
    @staticmethod
    def query() -> str:
        fragment = """ 
            fragment query_fragment on payloadtype {
              id
              agent_type
              deleted
              name
              supported_os
            }"""
        return fragment
