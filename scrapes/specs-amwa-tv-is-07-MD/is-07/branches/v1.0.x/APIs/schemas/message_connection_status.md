{
"$id": "https://www.amwa.tv/event\_and\_tally/message\_connection\_status.json",
"$schema": "http://json-schema.org/draft-04/schema#",
"description": "Message that indicates the status of the connection between the MQTT client and the broker. If connection status messages are used, the publishing topic is connection specific and must be specified in the connection\_status\_broker\_topic parameter of the MQTT IS-05 transport parameters object. The client must publish this message with the RETAIN flag set, after opening the connection to the broker and before closing the connection normally. The client must also configure a retained Will Message indicating it is disconnected.",
"properties": {
"active": {
"description": "A boolean value showing whether the MQTT client is connected to the broker.",
"type": "boolean"
},
"message\_type": {
"description": "A fixed string showing this is a connection status message",
"pattern": "^connection\_status$",
"type": "string"
}
},
"required": [
"message\_type",
"active"
],
"title": "Connection status message",
"type": "object"
}