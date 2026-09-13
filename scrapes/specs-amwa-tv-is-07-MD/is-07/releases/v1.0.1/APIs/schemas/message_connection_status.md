{
"$id": "https://www.amwa.tv/event\_and\_tally/message\_connection\_status.json",
"$schema": "http://json-schema.org/draft-04/schema#",
"type": "object",
"description": "Message that indicates the status of the connection between the MQTT client and the broker. The topic used is connection specific and has to be specified in the connection\_status\_broker\_topic parameter of the MQTT IS-05 transport parameters object. The client should publish this message with the RETAIN flag set, after opening the connection to the broker and before closing the connection normally. The client should also configure a retained Will Message indicating it is disconnected.",
"title": "Connection status message",
"required": [
"message\_type",
"active"
],
"properties": {
"message\_type": {
"description": "A fixed string showing this is a connection status message",
"type": "string",
"pattern": "^connection\_status$"
},
"active": {
"description": "A boolean value showing whether the MQTT client is connected to the broker.",
"type": "boolean"
}
}