{
"$id": "https://www.amwa.tv/event\_and\_tally/sender\_transport\_params\_ext.json",
"$schema": "http://json-schema.org/draft-04/schema#",
"description": "Describes external Sender transport parameters defined for IS-07 NMOS Event & Tally specification. The constraints in this schema are minimum constraints, but may be further constrained at the constraints endpoint.",
"properties": {
"ext\_is\_07\_rest\_api\_url": {
"description": "the URL for the Events API resource for the associated source",
"format": "uri",
"type": "string"
},
"ext\_is\_07\_source\_id": {
"description": "ID of the related source",
"pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
"type": "string"
}
},
"title": "External Sender Transport Parameters",
"type": "object"
}