class CallbackFragments:
    @staticmethod
    def query() -> str:
        fragment = """ 
            fragment query_fragment on callback {
              id
              display_id
              agent_callback_id
              init_callback
              last_checkin
              user
              host
              pid
              ip
              external_ip
              process_name
              description
              active
              registered_payload_id
              integrity_level
              locked
              locked_operator_id
              operator_id
              operation {
                id
                name
              }
              os
              architecture
              domain
              extra_info
              sleep_info
              timestamp
              payload {
                id
                uuid
                payloadtype {
                  name
                }
              }
            }"""
        return fragment