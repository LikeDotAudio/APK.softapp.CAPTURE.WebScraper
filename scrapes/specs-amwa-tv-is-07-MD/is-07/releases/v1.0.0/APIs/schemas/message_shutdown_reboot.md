{
"$id": "https://www.amwa.tv/event\_and\_tally/message\_shutdown\_reboot.json",
"$schema": "http://json-schema.org/draft-04/schema#",
"description": "Message that gets sent out when the device start a shutdown or reboot process",
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
"description": "A fixed string showing this is a reboot or a shutdown message",
"pattern": "^reboot|shutdown$",
"type": "string"
},
"timing": {
"description": "Object describing event timing",
"properties": {
"creation\_timestamp": {
"description": "String formatted TAI timestamp (:) indicating when the message was created",
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
"message\_type"
],
"title": "Shutdown and reboot message",
"type": "object"
}