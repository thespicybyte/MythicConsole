class TaskFragments:
    @staticmethod
    def query() -> str:
        fragment = """
            fragment query_fragment on task {
              id
              agent_task_id
              display_id
              command_id
              command_name
              params
              operation_id
              response_count
              completed
              comment
              timestamp
              stdout
              stderr
              status
              operator {
                id
                username
              }
              callback {
                id
                display_id
                agent_callback_id
                host
                payload {
                  payloadtype {
                    name
                  }
                }
              }
            }
        """
        return fragment
