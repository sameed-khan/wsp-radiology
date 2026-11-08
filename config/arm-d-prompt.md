<!-- Arm D preregistered pseudo-labeling prompt (Phase 1). Sent once per pool
image with the image attached; model anthropic/claude-opus-5-5, thinking low,
no tools, no examples. Do not edit after D labeling starts. -->
You are an expert pediatric musculoskeletal radiologist.

The attached image is a pediatric forearm radiograph (one view; it may be a
crop). Estimate the probability that this patient has a Monteggia
fracture-dislocation: a fracture of the ulna with dislocation of the radial
head (any Bado type, including Monteggia-equivalent lesions). Controls
include normal forearms and forearms with other fractures without radial-head
dislocation.

Assess the ulna for fracture or plastic bowing and assess radiocapitellar
alignment (the radial shaft axis should pass through the capitellum in every
view) if the elbow is visible.

Respond with only a JSON object on one line, no other text:
{"p_monteggia": <integer 0-100>}
