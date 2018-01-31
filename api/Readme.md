API tools collection
====================

Academy games analysis
----------------------

Work in progress tool to read player and game data from Academy (Mobile) games
and create player statistics. Currently all data is downloaded and parsed on
every invocation. Also there is no actual output yet.

Overall result structure:
  * For games:
    * Game ID
    * Sector name
    * Game status (joining, runnng, finished, etc.)
    * Creation and end dates
    * Final turn number
  * For players:
    * Dict structure holding player names as main key
    * per player holidng data for each game ID they joined
    * per game ID information on
      * status (alive, dropped, resigned, etc.)
      * final rank
      * final score (selected fields like ship count, military % etc.)

Next steps:
  * Serialize the data
  * Download and (re-)parse only when data changed
  * Export CSV files for different data views
  * Long term:
    * Parametrize CSV output
    * Integrate into Pandas
    * Make this a webservice
