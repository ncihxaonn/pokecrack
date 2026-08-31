"""Reviewed ISO 3166-1 alpha-2 allowlist mirrored from the database catalog."""

ISO_ALPHA2_CODES = frozenset(
    """
AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ
BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ BR BS BT BV BW BY BZ
CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ
DE DJ DK DM DO DZ
EC EE EG EH ER ES ET
FI FJ FK FM FO FR
GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY
HK HM HN HR HT HU
ID IE IL IM IN IO IQ IR IS IT
JE JM JO JP
KE KG KH KI KM KN KP KR KW KY KZ
LA LB LC LI LK LR LS LT LU LV LY
MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW MX MY MZ
NA NC NE NF NG NI NL NO NP NR NU NZ
OM
PA PE PF PG PH PK PL PM PN PR PS PT PW PY
QA
RE RO RS RU RW
SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV SX SY SZ
TC TD TF TG TH TJ TK TL TM TN TO TR TT TV TW TZ
UA UG UM US UY UZ
VA VC VE VG VI VN VU
WF WS
YE YT
ZA ZM ZW
""".split()
)

if len(ISO_ALPHA2_CODES) != 249:  # pragma: no cover - import-time drift guard
    raise RuntimeError("ISO alpha-2 allowlist must contain exactly 249 codes")

_CANONICAL_COUNTRY_ROWS = """
AD\tAndorra
AE\tUnited Arab Emirates
AF\tAfghanistan
AG\tAntigua & Barbuda
AI\tAnguilla
AL\tAlbania
AM\tArmenia
AO\tAngola
AQ\tAntarctica
AR\tArgentina
AS\tAmerican Samoa
AT\tAustria
AU\tAustralia
AW\tAruba
AX\tÅland Islands
AZ\tAzerbaijan
BA\tBosnia & Herzegovina
BB\tBarbados
BD\tBangladesh
BE\tBelgium
BF\tBurkina Faso
BG\tBulgaria
BH\tBahrain
BI\tBurundi
BJ\tBenin
BL\tSt. Barthélemy
BM\tBermuda
BN\tBrunei
BO\tBolivia
BQ\tCaribbean Netherlands
BR\tBrazil
BS\tBahamas
BT\tBhutan
BV\tBouvet Island
BW\tBotswana
BY\tBelarus
BZ\tBelize
CA\tCanada
CC\tCocos (Keeling) Islands
CD\tCongo - Kinshasa
CF\tCentral African Republic
CG\tCongo - Brazzaville
CH\tSwitzerland
CI\tCôte d’Ivoire
CK\tCook Islands
CL\tChile
CM\tCameroon
CN\tChina
CO\tColombia
CR\tCosta Rica
CU\tCuba
CV\tCape Verde
CW\tCuraçao
CX\tChristmas Island
CY\tCyprus
CZ\tCzechia
DE\tGermany
DJ\tDjibouti
DK\tDenmark
DM\tDominica
DO\tDominican Republic
DZ\tAlgeria
EC\tEcuador
EE\tEstonia
EG\tEgypt
EH\tWestern Sahara
ER\tEritrea
ES\tSpain
ET\tEthiopia
FI\tFinland
FJ\tFiji
FK\tFalkland Islands
FM\tMicronesia
FO\tFaroe Islands
FR\tFrance
GA\tGabon
GB\tUnited Kingdom
GD\tGrenada
GE\tGeorgia
GF\tFrench Guiana
GG\tGuernsey
GH\tGhana
GI\tGibraltar
GL\tGreenland
GM\tGambia
GN\tGuinea
GP\tGuadeloupe
GQ\tEquatorial Guinea
GR\tGreece
GS\tSouth Georgia & South Sandwich Islands
GT\tGuatemala
GU\tGuam
GW\tGuinea-Bissau
GY\tGuyana
HK\tHong Kong SAR China
HM\tHeard & McDonald Islands
HN\tHonduras
HR\tCroatia
HT\tHaiti
HU\tHungary
ID\tIndonesia
IE\tIreland
IL\tIsrael
IM\tIsle of Man
IN\tIndia
IO\tBritish Indian Ocean Territory
IQ\tIraq
IR\tIran
IS\tIceland
IT\tItaly
JE\tJersey
JM\tJamaica
JO\tJordan
JP\tJapan
KE\tKenya
KG\tKyrgyzstan
KH\tCambodia
KI\tKiribati
KM\tComoros
KN\tSt. Kitts & Nevis
KP\tNorth Korea
KR\tSouth Korea
KW\tKuwait
KY\tCayman Islands
KZ\tKazakhstan
LA\tLaos
LB\tLebanon
LC\tSt. Lucia
LI\tLiechtenstein
LK\tSri Lanka
LR\tLiberia
LS\tLesotho
LT\tLithuania
LU\tLuxembourg
LV\tLatvia
LY\tLibya
MA\tMorocco
MC\tMonaco
MD\tMoldova
ME\tMontenegro
MF\tSt. Martin
MG\tMadagascar
MH\tMarshall Islands
MK\tNorth Macedonia
ML\tMali
MM\tMyanmar (Burma)
MN\tMongolia
MO\tMacao SAR China
MP\tNorthern Mariana Islands
MQ\tMartinique
MR\tMauritania
MS\tMontserrat
MT\tMalta
MU\tMauritius
MV\tMaldives
MW\tMalawi
MX\tMexico
MY\tMalaysia
MZ\tMozambique
NA\tNamibia
NC\tNew Caledonia
NE\tNiger
NF\tNorfolk Island
NG\tNigeria
NI\tNicaragua
NL\tNetherlands
NO\tNorway
NP\tNepal
NR\tNauru
NU\tNiue
NZ\tNew Zealand
OM\tOman
PA\tPanama
PE\tPeru
PF\tFrench Polynesia
PG\tPapua New Guinea
PH\tPhilippines
PK\tPakistan
PL\tPoland
PM\tSt. Pierre & Miquelon
PN\tPitcairn Islands
PR\tPuerto Rico
PS\tPalestinian Territories
PT\tPortugal
PW\tPalau
PY\tParaguay
QA\tQatar
RE\tRéunion
RO\tRomania
RS\tSerbia
RU\tRussia
RW\tRwanda
SA\tSaudi Arabia
SB\tSolomon Islands
SC\tSeychelles
SD\tSudan
SE\tSweden
SG\tSingapore
SH\tSt. Helena
SI\tSlovenia
SJ\tSvalbard & Jan Mayen
SK\tSlovakia
SL\tSierra Leone
SM\tSan Marino
SN\tSenegal
SO\tSomalia
SR\tSuriname
SS\tSouth Sudan
ST\tSão Tomé & Príncipe
SV\tEl Salvador
SX\tSint Maarten
SY\tSyria
SZ\tEswatini
TC\tTurks & Caicos Islands
TD\tChad
TF\tFrench Southern Territories
TG\tTogo
TH\tThailand
TJ\tTajikistan
TK\tTokelau
TL\tTimor-Leste
TM\tTurkmenistan
TN\tTunisia
TO\tTonga
TR\tTürkiye
TT\tTrinidad & Tobago
TV\tTuvalu
TW\tTaiwan
TZ\tTanzania
UA\tUkraine
UG\tUganda
UM\tU.S. Outlying Islands
US\tUnited States
UY\tUruguay
UZ\tUzbekistan
VA\tVatican City
VC\tSt. Vincent & Grenadines
VE\tVenezuela
VG\tBritish Virgin Islands
VI\tU.S. Virgin Islands
VN\tVietnam
VU\tVanuatu
WF\tWallis & Futuna
WS\tSamoa
YE\tYemen
YT\tMayotte
ZA\tSouth Africa
ZM\tZambia
ZW\tZimbabwe
""".strip()

CANONICAL_COUNTRY_NAMES = dict(
    row.split("\t", maxsplit=1) for row in _CANONICAL_COUNTRY_ROWS.splitlines()
)

if frozenset(CANONICAL_COUNTRY_NAMES) != ISO_ALPHA2_CODES:  # pragma: no cover
    raise RuntimeError("canonical country-name catalog must match the ISO allowlist")
