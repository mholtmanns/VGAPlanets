The data file
=============

By default running `apiaccess.py` will populate the file `player_data.json`.

If debugging the module you might want to replace the call to
```get_academy_games(gamekeys)```
with
```get_academy_games(gamekeys, maxgames = <N>)```
where `N` is the maximum nuber of games you want to work with right now.

The issue with this is that the PlanetsNU API returns the game information in random order as well. That means over consecutive calls you will likely not get the exact game information returned.

So either you fill the stored data regardless with the newly found game info, or you simply ignore the API data if you already have the desired number of games in your stored file. Here we default to ignore the differing data in case we just use a subset of all games.

JSON dump pitfalls
------------------

* Dicts can have `int` keys, but `json.dump()` writes it as `str` to disk.