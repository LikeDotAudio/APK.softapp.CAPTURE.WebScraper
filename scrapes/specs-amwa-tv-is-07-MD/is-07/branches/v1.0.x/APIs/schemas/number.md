{
"$id": "https://www.amwa.tv/event\_and\_tally/number.json",
"$schema": "http://json-schema.org/draft-04/schema#",
"description": "Number",
"properties": {
"scale": {
"description": "Denominator for rational number representation (default = 1)",
"minimum": 1,
"type": "integer"
},
"value": {
"description": "Number value",
"type": "number"
}
},
"required": [
"value"
],
"type": "object"
}