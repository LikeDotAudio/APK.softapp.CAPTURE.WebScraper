{
"$id": "https://www.amwa.tv/event\_and\_tally/command\_subscription.json",
"$schema": "http://json-schema.org/draft-04/schema#",
"description": "Command that subscribes the receiver to receive the state change messages for the specified sources",
"properties": {
"command": {
"description": "A fixed string showing this is a subscription command",
"pattern": "^subscription$",
"type": "string"
},
"sources": {
"description": "A list of Event & Tally sources to subscribe to",
"items": {
"description": "IDs of the Event & Tally compatible sources",
"pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
"type": "string"
},
"minItems": 0,
"type": "array",
"uniqueItems": true
}
},
"required": [
"command",
"sources"
],
"title": "Subscription command",
"type": "object"
}