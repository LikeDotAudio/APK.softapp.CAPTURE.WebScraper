{
"$id": "https://www.amwa.tv/event\_and\_tally/message.json",
"$schema": "http://json-schema.org/draft-04/schema#",
"type": "object",
"description": "Allowed messages (communication from the sender to the receiver)",
"title": "Message",
"oneOf": [{
"$ref": "event.json"
}, {
"$ref": "message\_connection\_status.json"
}, {
"$ref": "message\_health.json"
}, {
"$ref": "message\_shutdown\_reboot.json"
}]
}