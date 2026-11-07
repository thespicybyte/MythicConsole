class OperationFragments:
    @staticmethod
    def query() -> str:
        fragment = """ 
            fragment query_fragment on operation {
                id
                name
                admin_id
                alert_count
                channel
                complete
                deleted
                webhook
                disabledcommandsprofiles {
                    id
                }
                callbacks {
                    agent_callback_id
                }
                operators {
                    id
                }
            }"""
        return fragment