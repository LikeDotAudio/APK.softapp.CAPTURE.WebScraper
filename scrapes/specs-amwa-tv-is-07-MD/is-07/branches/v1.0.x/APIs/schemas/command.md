{
"$id": "https://www.amwa.tv/event\_and\_tally/command.json",
"$schema": "http://json-schema.org/draft-04/schema#",
"type": "object",
"description": "Allowed commands (communication from the receiver to the sender)",
"title": "Command",
"oneOf": [{
"$ref": "command\_health.json"
}, {
"$ref": "command\_subscription.json"
}]
}