class UserFragments:
    @staticmethod
    def query() -> str:
        return """ fragment query_fragment on operator  {
            id
            username
            admin
            creation_time
            last_login
            active
            view_utc_time
            deleted
            current_operation_id
            operation {
                id
                name
            }
        } """
