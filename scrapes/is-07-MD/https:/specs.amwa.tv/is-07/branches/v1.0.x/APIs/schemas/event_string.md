{
"$id": "https://www.amwa.tv/event\_and\_tally/event\_string.json",
"$schema": "http://json-schema.org/draft-04/schema#",
"type": "object",
"description": "Describes an event with string payload",
"title": "String event",
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
"pattern": "^string(\\/[^\\s\\/]+)\*$"
},
"payload": {
"description": "String payload",
"type": "object",
"required": [
"value"
],
"properties": {
"value": {
"description": "String value",
"type": "string"
}
}
}
}
}
]
}