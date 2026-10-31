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

    @staticmethod
    def build_parameters_fragment() -> str:
        fragment = """
            fragment build_parameters_fragment on buildparameter {
              name
              description
              parameter_type
              default_value
              required
              choices
              format_string
              verifier_regex
              crypto_type
              randomize
              group_name
            }"""
        return fragment
