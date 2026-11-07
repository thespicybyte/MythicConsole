from ..c2_profile.fragments import C2ProfileFragments


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
              note
              container_running
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

    @staticmethod
    def supported_c2_fragment() -> str:
        fragment = f"""
            fragment supported_c2_fragment on payloadtype {{
              supports_multiple_c2_in_build
              payloadtypec2profiles(where: {{c2profile: {{deleted: {{_eq: false}}}}}}) {{
                c2profile {{
                  ...query_fragment
                }}
              }}
            }}
            {C2ProfileFragments.query()}"""
        return fragment
