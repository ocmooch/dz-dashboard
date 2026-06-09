"""Historical fantasy team names recovered from pre-merge NFL.com season rows.

The live Phase 1 DB currently carries current/canonical names for many past
team-season rows after owner identity repair. For player ownership timelines,
the period-correct label is the NFL.com season/team-slot name, keyed by
``(season_year, team_abbrev)``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ff_pipeline.repository.models import Team


_RAW_NAMES = """
2010	1	Super Red Espresso Snowflake
2010	2	DOOKS
2010	3	ThisTeamMakesSullyNervous
2010	4	The Monks
2010	5	your MEAT all over sum1s grill
2010	6	Heathcliff's Haiku Warriors
2010	7	fire in the taco bell
2010	8	Down Like A Clown Pussy
2010	9	Fie
2010	10	whats going on here
2010	11	Final Fantasy Football
2010	12	IAMTHEOMEN
2011	1	Talkin About Practice
2011	2	Greasy Grundle Dirtyburgers
2011	3	IAMTHESACKO
2011	4	Egg McSullivan
2011	5	The Sneaky Js
2011	6	The Renegades of Funk
2011	7	I just blue myself
2011	8	Paid for by Sen Bob Penisburgh
2011	9	Papa Fies SteakhouseExperience
2011	10	is this whats going on here
2011	11	The Mammalian Aliens
2011	12	IAMTHEOMEN
2012	1	Anything is Possible
2012	2	Golden Tatertots
2012	3	Sulladismichaelbushleague
2012	4	Sulladin's Salty Mujahideen
2012	5	Tainted Basil
2012	6	Walter's White Ricin
2012	7	HoneyBadgerSwagger
2012	8	No Sweat Just Chile
2012	9	Papa Fies Back for Seconds
2012	10	what IS the shawshank rdmption
2012	11	Robtimus Prime
2012	12	I AM CHANGED
2013	1	Omaaha Spuki Sushi
2013	2	Roddy's White Walkers
2013	3	Salty Caramel Sullad
2013	4	All About The Gains
2013	5	Draft Punk
2013	6	Tolzien's Trash Talkers
2013	7	super fancy cheeses
2013	8	Casquango Unchained
2013	9	House Fie Fie of Steel
2013	10	1000 tickets
2013	11	Corn on the Rob
2013	12	Eye C U
2014	1	Crystal Blue Persuaders
2014	2	puglISIS
2014	3	IStoleSulladsPick
2014	4	The Northvale Scumbags
2014	5	The King in the Northvale
2014	6	Bed Forbath and Beyond
2014	7	Arya Ready For Some Football
2014	8	The King of the Tiebreakers
2014	9	The Iron Bank of Fie Fie
2014	10	THE GRILL
2014	11	Attack of the Killer Robbot
2014	12	Drake's New Favorite Team
2015	1	The Unfugazables
2015	2	Say My Namath
2015	3	Snow and Mirrors
2015	4	Flappy Papi's Plum Smugglers
2015	5	Mint Chocolate Chip Kelly
2015	6	The Marc TrestMANBEARPIGS
2015	7	Show me your TDs
2015	8	Hurtin for a Casquirtin
2015	9	The Order of the Fienix
2015	10	Sheriff John Brown
2015	11	Robamacare
2015	12	Bruce Jenner DJ's
2016	1	A Gurley Has No Name
2016	2	Pugleesi - Brother of Flagons
2016	3	I just blue myself
2016	4	Salt in the Woobanger
2016	5	I Need Mo Allowance
2016	6	I DON'T Like Donuts
2016	7	Matt Asiago
2016	8	Bada Bing Crosby
2016	9	Kahl Fiefie's Bloodriders
2016	10	Commissioner J Gordon
2016	11	Robi-Wan Kenobi
2016	12	Wilfork On 1st Date
2017	1	Brotherhood Without Bungalows
2017	2	The End of an Error
2017	3	Chicken Ks All Day
2017	4	Hillary's Cankle Breakers
2017	5	The Silver Spoon Motherfuckers
2017	6	CAPPe Diem- Seize the Day
2017	7	Demaryius Targaryen
2017	8	Chip Cootahson
2017	9	Fie of Steel
2017	10	Jeffis Winsaton
2017	11	Robald McDoland
2017	12	OJ is a Freeman
2018	1	Chicken Teriyaki Boys
2018	2	Da BearZ and the Melvin Fair
2018	3	Chicken Ks All Day
2018	4	Doughy Donald's Rushin' Trolls
2018	5	Now Your Thinking With Bortles
2018	6	WayneGallman Leviosa
2018	7	Super Coopers
2018	8	Scissor Me Sertxes
2018	9	Agents of FIE
2018	10	do the SHAWdy lean
2018	11	ROBJECTION
2018	12	Le'veon bells on your chin
2019	1	Cap'n Cook's Chili P
2019	2	CROWDEREDDDD TOASTTTT MANNNNNN
2019	3	The Grim SiLLeeper
2019	4	Stevie Wonders Blindside Blitz
2019	5	13-15 Feral Ball Hogs
2019	6	The Brigands of Braciole
2019	7	TopGoff
2019	8	The Fightin Funkhousers
2019	9	FIEFIEANA JONES
2019	10	Natty Dreads
2019	11	The Roblet of Fire
2019	12	Half Bakered
2020	1	Chankanda Forever
2020	2	The Legend of Drubken Drafster
2020	3	The Grim SiLLeeper
2020	4	Knights Of Carumbus
2020	5	New Jersey Knuckleheads
2020	6	WYLD STALLYNS
2020	7	New Team Name
2020	8	Flock of Seagals
2020	9	Fiemishs Crusty Crew
2020	10	K1 Racing
2020	11	Shish Karob
2020	12	Tennessee Tuggernuggetz
2021	1	The Chandalorian
2021	2	DuDu Shit-Pooster
2021	3	The Grim SiLLeeper
2021	4	Seeing Ghosts 'n' Stuff
2021	5	AH-WHATS UP SALEHHHHH
2021	6	Buy Camp Krampus
2021	7	Christian McCaffDairyFree
2021	8	The Hans Team
2021	9	The Fie Machines
2021	10	swaggy anime watcher
2021	11	Broccoli Rob
2021	12	Jonathan Taylor Swifties
2022	1	Ice Station Zebra
2022	2	Smokin' AJ
2022	3	The Grim SiLLeeper
2022	4	CMC Rules Everything Around Me
2022	5	So What-No Fuckin Ziti Now
2022	6	Younghoe Kooloo Limpah
2022	7	House of the Droggenburg
2022	8	Smokin Dabolls
2022	9	Feast of FIES
2022	10	Smokin Doubs
2022	11	Robra Kai
2022	12	King Henry the 8ball
2023	1	Car-Coochie Board
2023	2	Mock the Clock
2023	3	ILLS REVENGE
2023	4	Boomer Bust Deez Nuts
2023	5	The Oily Boyd Gets the Woym
2023	6	There's Pizza in the Mailbox
2023	7	Winnie
2023	8	Fred Jacksons Revenge
2023	9	Papa Fies Dumpling House
2023	10	Red Jeff
2023	11	SpongeRob
2023	12	DO IT FOR ILL
2024	1	Just a Chill Guy Sneaking In
2024	2	Amon-Ra St-St-St-Stutter Steps
2024	3	JUMBO IS ON THE CLOCK
2024	4	Say Hello To The Bad Guy
2024	5	Senses Fail to Convert
2024	6	Putting the CAP in CHAMP
2024	7	1000 Bottles of Baby Boyle
2024	8	Still the Defending Champ
2024	9	Fies Hawaiian Experiments
2024	10	Montgomery Burns Football Team
2024	11	Robtisserie Chicken
2024	12	IWASGONAPLAYTEFORTHEJETS
2025	1	Cream of the C
2025	2	The ESPNstein Files
2025	3	JFCFPWCPGAWWLTDOSGT
2025	4	The Wizard Of BAA'z
2025	5	The Princess McBride
2025	6	FROM FIRST TO LAST
2025	7	Rev Russell's Sunday Service
2025	8	Character Zero RB
2025	9	F this Tenacious Fie
2025	10	London on da Track
2025	11	ROBZILLA
2025	12	Batesohardithurts
"""


HISTORICAL_TEAM_NAMES: dict[tuple[int, str], str] = {}
for _line in _RAW_NAMES.strip().splitlines():
    _year, _slot, _name = _line.split("\t", 2)
    HISTORICAL_TEAM_NAMES[(int(_year), _slot)] = _name


def period_team_name(team: Team, season_year: int) -> str | None:
    """Return a period-correct fantasy team name when the slot/year is known."""
    if team.team_abbrev is None:
        return team.team_name
    return HISTORICAL_TEAM_NAMES.get((season_year, str(team.team_abbrev)), team.team_name)
