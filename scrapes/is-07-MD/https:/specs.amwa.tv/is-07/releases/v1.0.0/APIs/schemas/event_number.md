{
"$id": "https://www.amwa.tv/event\_and\_tally/event\_number.json",
"$schema": "http://json-schema.org/draft-04/schema#",
"type": "object",
"description": "Describes an event with Number payload",
"title": "Number event",
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
"pattern": "^number(?:\\/[a-zA-Z\_\\-])\*$"
},
"payload": { "$ref": "number.json" }
}
}
]
}