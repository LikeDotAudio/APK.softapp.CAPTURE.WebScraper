{
"$id": "https://www.amwa.tv/event\_and\_tally/type.json",
"$schema": "http://json-schema.org/draft-04/schema#",
"type": "object",
"description": "Type definition",
"title": "Type definition",
"oneOf": [
{ "$ref": "type\_boolean.json" },
{ "$ref": "type\_boolean\_enum.json" },
{ "$ref": "type\_number.json" },
{ "$ref": "type\_number\_enum.json" },
{ "$ref": "type\_string.json" },
{ "$ref": "type\_string\_enum.json" }
]
}