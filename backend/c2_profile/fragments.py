class C2ProfileFragments:
    @staticmethod
    def query() -> str:
        fragment = """
            fragment query_fragment on c2profile {
              id
              name
              is_p2p
              c2profileparameters {
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
              }
            }"""
        return fragment
