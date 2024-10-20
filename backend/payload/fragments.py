class PayloadFragments:
    @staticmethod
    def query() -> str:
        fragment = """
            fragment query_fragment on payload {
              id
              build_message
              build_phase
              build_stderr
              build_stdout
              deleted
              description
              file_id
              uuid
              creation_time
              os
              timestamp
              operator {
                id
                username
              }
              operation {
                id
                name
              }
              payloadtype {
                name
              }
              payloadc2profiles {
                c2profile {
                  name
                }
              }
            }
        """
        return fragment
