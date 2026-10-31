{
"$id": "https://www.amwa.tv/event\_and\_tally/type\_boolean\_enum.json",
"$schema": "http://json-schema.org/draft-04/schema#",
"additionalProperties": false,
"description": "Type definition for the boolean enum type",
"properties": {
"type": {
"description": "Base type name",
"enum": [
"boolean"
],
"type": "string"
},
"values": {
"description": "List of allowed values",
"items": {
"properties": {
"description": {
"description": "Enum description",
"type": "string"
},
"label": {
"description": "Enum label",
"type": "string"
},
"value": {
"description": "Enum value",
"type": "boolean"
}
},
"required": [
"value",
"label",
"description"
],
"title": "Enum Element",
"type": "object"
},
"type": "array"
}
},
"required": [
"type",
"values"
],
"title": "Boolean Enum Type",
"type": "object"
}