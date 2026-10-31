{
"$id": "https://www.amwa.tv/event\_and\_tally/event\_object.json",
"$schema": "http://json-schema.org/draft-04/schema#",
"type": "object",
"description": "Describes an event with object payload",
"title": "Object event",
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
"pattern": "^object(\\/[^\\s\\/]+)\*$"
},
"payload": {
"description": "Object payload",
"type": "object"
}
}
}
]
}