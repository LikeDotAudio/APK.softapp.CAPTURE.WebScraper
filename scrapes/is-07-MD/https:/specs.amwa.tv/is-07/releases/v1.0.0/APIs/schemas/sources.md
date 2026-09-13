{
"$id": "https://www.amwa.tv/event\_and\_tally/sources.json",
"$schema": "http://json-schema.org/draft-04/schema#",
"description": "A list of Event & Tally Source resources",
"items": {
"description": "IDs of the Event & Tally compatible sources",
"pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\\/$",
"type": "string"
},
"minItems": 0,
"title": "Collection of Event & Tally Sources",
"type": "array",
"uniqueItems": true
}