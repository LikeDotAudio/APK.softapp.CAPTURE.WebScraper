{
"$id": "https://www.amwa.tv/event\_and\_tally/event\_boolean.json",
"$schema": "http://json-schema.org/draft-04/schema#",
"type": "object",
"description": "Describes an event with boolean payload",
"title": "Boolean event",
"allOf": [
{ "$ref": "event\_core.json" },
{
"type": "object",
"required": [
"event\_type",
"payload"
],
"properties": {
"event\_type": {
"description": "Event type",
"type": "string",
"pattern": "^boolean(?:\\/[a-zA-Z\_\\-])\*$"
},
"payload": {
"description": "Boolean payload",
"type": "object",
"required": [
"value"
],
"properties": {
"value": {
"description": "Boolean value",
"type": "boolean"
}
}
}
}
}
]
}