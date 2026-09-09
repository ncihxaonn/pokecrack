"""Country/area research targets, never observations or city-level records.

UN M49 regions, checked 2026-09-09:
https://unstats.un.org/unsd/methodology/m49/overview/
TW is retained as the existing application's distinct product-market bucket.
Names are short display labels; grouping is statistical, not a sovereignty claim.
"""

# Append phases without renaming/reordering retained country reports.
REGION_ORDER = ("asia", "oceania", "europe", "africa", "north-america", "latin-america", "antarctica")
_TARGETS = {
    "asia": """MY|Malaysia
VN|Viet Nam
PH|Philippines
HK|Hong Kong
IN|India
MO|Macao
AF|Afghanistan
AM|Armenia
AZ|Azerbaijan
BH|Bahrain
BD|Bangladesh
BT|Bhutan
BN|Brunei Darussalam
KH|Cambodia
CN|China
CY|Cyprus
GE|Georgia
ID|Indonesia
IR|Iran
IQ|Iraq
IL|Israel
JP|Japan
JO|Jordan
KZ|Kazakhstan
KW|Kuwait
KG|Kyrgyzstan
LA|Lao People's Democratic Republic
LB|Lebanon
MV|Maldives
MN|Mongolia
MM|Myanmar
NP|Nepal
KP|Democratic People's Republic of Korea
OM|Oman
PK|Pakistan
PS|State of Palestine
QA|Qatar
SA|Saudi Arabia
SG|Singapore
KR|Republic of Korea
LK|Sri Lanka
SY|Syrian Arab Republic
TW|Taiwan
TJ|Tajikistan
TH|Thailand
TL|Timor-Leste
TR|Türkiye
TM|Turkmenistan
AE|United Arab Emirates
UZ|Uzbekistan
YE|Yemen""",
    "oceania": """AU|Australia
NZ|New Zealand
FJ|Fiji
PG|Papua New Guinea
SB|Solomon Islands
VU|Vanuatu
WS|Samoa
TO|Tonga
TV|Tuvalu
KI|Kiribati
NR|Nauru
PW|Palau
FM|Micronesia
MH|Marshall Islands
AS|American Samoa
CK|Cook Islands
CX|Christmas Island
CC|Cocos (Keeling) Islands
PF|French Polynesia
GU|Guam
HM|Heard Island and McDonald Islands
NC|New Caledonia
NU|Niue
NF|Norfolk Island
MP|Northern Mariana Islands
PN|Pitcairn
TK|Tokelau
UM|United States Minor Outlying Islands
WF|Wallis and Futuna Islands""",
    "europe": """FR|France
DE|Germany
IT|Italy
ES|Spain
GB|United Kingdom
AL|Albania
AD|Andorra
AT|Austria
BY|Belarus
BE|Belgium
BA|Bosnia and Herzegovina
BG|Bulgaria
HR|Croatia
CZ|Czechia
DK|Denmark
EE|Estonia
FI|Finland
GR|Greece
HU|Hungary
IS|Iceland
IE|Ireland
LV|Latvia
LI|Liechtenstein
LT|Lithuania
LU|Luxembourg
MT|Malta
MD|Republic of Moldova
MC|Monaco
ME|Montenegro
NL|Netherlands
MK|North Macedonia
NO|Norway
PL|Poland
PT|Portugal
RO|Romania
RU|Russian Federation
SM|San Marino
RS|Serbia
SK|Slovakia
SI|Slovenia
SE|Sweden
CH|Switzerland
UA|Ukraine
VA|Holy See
AX|Åland Islands
FO|Faroe Islands
GG|Guernsey
GI|Gibraltar
IM|Isle of Man
JE|Jersey
SJ|Svalbard and Jan Mayen Islands""",
    "africa": """ZA|South Africa
EG|Egypt
KE|Kenya
NG|Nigeria
MA|Morocco
DZ|Algeria
AO|Angola
BJ|Benin
BW|Botswana
BF|Burkina Faso
BI|Burundi
CV|Cabo Verde
CM|Cameroon
CF|Central African Republic
TD|Chad
KM|Comoros
CG|Congo
CD|Democratic Republic of the Congo
CI|Côte d'Ivoire
DJ|Djibouti
GQ|Equatorial Guinea
ER|Eritrea
SZ|Eswatini
ET|Ethiopia
GA|Gabon
GM|Gambia
GH|Ghana
GN|Guinea
GW|Guinea-Bissau
LS|Lesotho
LR|Liberia
LY|Libya
MG|Madagascar
MW|Malawi
ML|Mali
MR|Mauritania
MU|Mauritius
MZ|Mozambique
NA|Namibia
NE|Niger
RW|Rwanda
ST|Sao Tome and Principe
SN|Senegal
SC|Seychelles
SL|Sierra Leone
SO|Somalia
SS|South Sudan
SD|Sudan
TZ|United Republic of Tanzania
TG|Togo
TN|Tunisia
UG|Uganda
ZM|Zambia
ZW|Zimbabwe
IO|British Indian Ocean Territory
TF|French Southern Territories
YT|Mayotte
RE|Réunion
SH|Saint Helena
EH|Western Sahara""",
    "north-america": """US|United States of America
CA|Canada
BM|Bermuda
GL|Greenland
PM|Saint Pierre and Miquelon""",
    "latin-america": """MX|Mexico
BR|Brazil
AR|Argentina
CL|Chile
CO|Colombia
PE|Peru
AI|Anguilla
AG|Antigua and Barbuda
AW|Aruba
BS|Bahamas
BB|Barbados
BQ|Bonaire, Sint Eustatius and Saba
VG|British Virgin Islands
KY|Cayman Islands
CU|Cuba
CW|Curaçao
DM|Dominica
DO|Dominican Republic
GD|Grenada
GP|Guadeloupe
HT|Haiti
JM|Jamaica
MQ|Martinique
MS|Montserrat
PR|Puerto Rico
BL|Saint Barthélemy
KN|Saint Kitts and Nevis
LC|Saint Lucia
MF|Saint Martin (French Part)
VC|Saint Vincent and the Grenadines
SX|Sint Maarten (Dutch part)
TT|Trinidad and Tobago
TC|Turks and Caicos Islands
VI|United States Virgin Islands
BZ|Belize
CR|Costa Rica
SV|El Salvador
GT|Guatemala
HN|Honduras
NI|Nicaragua
PA|Panama
BO|Bolivia
BV|Bouvet Island
EC|Ecuador
FK|Falkland Islands (Malvinas)
GF|French Guiana
GY|Guyana
PY|Paraguay
GS|South Georgia and the South Sandwich Islands
SR|Suriname
UY|Uruguay
VE|Venezuela""",
    "antarctica": """AQ|Antarctica""",
}
REGIONS = {
    region: tuple(tuple(line.split("|")) for line in _TARGETS[region].splitlines())
    for region in REGION_ORDER
}
COUNTRIES = {code: name for targets in REGIONS.values() for code, name in targets}
COUNTRY_REGION = {code: region for region, targets in REGIONS.items() for code, _ in targets}
