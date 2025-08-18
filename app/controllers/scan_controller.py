from app.commands.scan.process_table_list import ProcessTableListCommand

from app.controllers.controller import Controller


class ScanController(Controller):
    """
    A controller for scanning the database.
    """
    def get_tables(self) -> list:
        return self.executor.execute_read(ProcessTableListCommand(database="app/data/data.db"))

    