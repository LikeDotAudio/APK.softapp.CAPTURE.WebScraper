{
"$id": "https://www.amwa.tv/event\_and\_tally/event\_core.json",
"$schema": "http://json-schema.org/draft-04/schema#",
"description": "Message that gets sent out when the source state changes",
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
"description": "ID of the source that holds the state that has changed",
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
"description": "A fixed string showing this is a state message",
"pattern": "^state$",
"type": "string"
},
"timing": {
"description": "Object describing event timing",
"properties": {
"action\_timestamp": {
"description": "String formatted TAI timestamp (:) indicating when the state change described in the event took or will take place",
"pattern": "^[0-9]+:[0-9]+$",
"type": "string"
},
"creation\_timestamp": {
"description": "String formatted TAI timestamp (:) indicating when the message was created",
"pattern": "^[0-9]+:[0-9]+$",
"type": "string"
},
"origin\_timestamp": {
"description": "String formatted TAI timestamp (:) indicating when the message that triggered this message (if any) was created",
"pattern": "^[0-9]+:[0-9]+$",
"type": "string"
}
},
"required": [
"creation\_timestamp"
],
"type": "object"
}
},
"required": [
"identity",
"timing",
"event\_type",
"payload",
"message\_type"
],
"title": "State change event",
"type": "object"
}