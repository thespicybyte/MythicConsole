class DisabledCommandsProfileFragments:
    @staticmethod
    def query() -> str:
        fragment = """
            fragment query_fragment on disabledcommandsprofile {
                id
                name
                command_id
                operation_id
                command {
                    id
                    cmd
                    payloadtype {
                        name
                    }
                }
                operatoroperations {
                    id
                    operator {
                        id
                        username
                    }
                }
            }"""
        return fragment
