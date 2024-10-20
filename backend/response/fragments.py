class ResponseFragments:
    @staticmethod
    def query() -> str:
        fragment = """
            fragment query_fragment on response {
              id
              task_id
              is_error
              operation_id
              response_text
            }
        """
        return fragment
