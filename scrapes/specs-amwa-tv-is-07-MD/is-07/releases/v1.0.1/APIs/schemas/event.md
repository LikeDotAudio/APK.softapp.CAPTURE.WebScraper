{
"$id": "https://www.amwa.tv/event\_and\_tally/event.json",
"$schema": "http://json-schema.org/draft-04/schema#",
"type": "object",
"description": "Message that gets sent out when the source state changes",
"title": "State change event",
"oneOf": [{
"$ref": "event\_boolean.json"
}, {
"$ref": "event\_number.json"
}, {
"$ref": "event\_string.json"
}, {
"$ref": "event\_object.json"
}]
}