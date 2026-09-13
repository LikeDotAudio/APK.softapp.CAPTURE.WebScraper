{
"$id": "https://www.amwa.tv/event\_and\_tally/message\_connection\_lost.json",
"$schema": "http://json-schema.org/draft-04/schema#",
"description": "Message that gets registered with the broker to send it out when the connection to the broker gets ungracefully closed",
"properties": {
"identity": {
"description": "Object describing event identity",
"properties": {
"flow\_id": {
"description": "ID of the flow carrying the message",
"pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
"type": "string"
},
"source\_id": {
"description": "ID of the source which identifies the emitter of the event",
"pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
"type": "string"
}
},
"required": [
"source\_id"
],
"type": "object"
},
"message\_type": {
"description": "A fixed string showing this is a connection lost message",
"pattern": "^connection\_lost$",
"type": "string"
}
},
"required": [
"identity",
"message\_type"
],
"title": "Connection lost message",
"type": "object"
}