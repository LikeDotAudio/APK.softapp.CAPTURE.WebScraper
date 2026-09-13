{
"$id": "https://www.amwa.tv/event\_and\_tally/type\_string.json",
"$schema": "http://json-schema.org/draft-04/schema#",
"additionalProperties": false,
"description": "Type definition for the string type",
"properties": {
"max\_length": {
"description": "Maximum string length",
"minimum": 1,
"type": "integer"
},
"min\_length": {
"description": "Minimum string length",
"minimum": 0,
"type": "integer"
},
"pattern": {
"description": "Regular expression constraining the value",
"type": "string"
},
"type": {
"description": "Base type name",
"enum": [
"string"
],
"type": "string"
}
},
"required": [
"type"
],
"title": "String Type",
"type": "object"
}