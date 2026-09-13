{
"$id": "https://www.amwa.tv/event\_and\_tally/message\_health.json",
"$schema": "http://json-schema.org/draft-04/schema#",
"description": "Message that gets sent out as the response to a health (heartbeat) command",
"properties": {
"message\_type": {
"description": "A fixed string showing this is a health message",
"pattern": "^health$",
"type": "string"
},
"timing": {
"description": "Object describing event timing",
"properties": {
"creation\_timestamp": {
"description": "String formatted TAI timestamp (:) indicating when the message was created",
"pattern": "^[0-9]+:[0-9]+$",
"type": "string"
},
"origin\_timestamp": {
"description": "String formatted TAI timestamp (:) copied from the incoming health command",
"pattern": "^[0-9]+:[0-9]+$",
"type": "string"
}
},
"required": [
"creation\_timestamp",
"origin\_timestamp"
],
"type": "object"
}
},
"required": [
"timing",
"message\_type"
],
"title": "Health message",
"type": "object"
}