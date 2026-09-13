{
"$id": "https://www.amwa.tv/event\_and\_tally/command\_health.json",
"$schema": "http://json-schema.org/draft-04/schema#",
"description": "Command that initiates a health message to be generated in order to check the state of the connection and the sender",
"properties": {
"command": {
"description": "A fixed string showing this is a health command",
"pattern": "^health$",
"type": "string"
},
"timestamp": {
"description": "String formatted TAI timestamp (:) indicating the time the command was issued",
"pattern": "^[0-9]+:[0-9]+$",
"type": "string"
}
},
"required": [
"command",
"timestamp"
],
"title": "Health command",
"type": "object"
}