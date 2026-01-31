Eioku: A Video Intelligence Platform for Editors

Codi Huston

Hackathon Participan...
16m

Posted in Primary Hackathon Channel
Hi everyone, my name is Codi! I was originally not going to be able to participate due to flames and chaos at work and personal life, however when the deadline was extended, I figured I might be able to deliver with the short amount of time I had. I was able to work on this over the course of about 12 days

Eioku is a video intelligence platform. It is designed with the intent to expedite the video editing process by enabling you to quickly find the right moments in a vast library of video content.

Demo: https://youtu.be/4DD5srIONn0?si=Gu8SvW-Tfy2J4M1d

[bkp](https://preservetube.com/watch?v=4DD5srIONn0)

Repo: https://github.com/codihuston/eioku

What differentiates Eioku from other similar tools is the ability to search and jump across videos at any point in time as opposed to a simple search gallery view. You can search across an array of indexes such as objects, on screen text, spoken words, gps/locations, etc. You can also download clips of your video. All inferencing is local. The search is currently full-text search, not semantic.

I reiterated in the architecture like 4 times which reduced the time to put effort into semantic search, and adding other types of inferences (known faces, emotion, music detection, action, color), and LLM integration. I finally landed on a data model that will make adding semantic search easier. I battled with enabling this to be zero-ops, self hosted, distributed worker support (gpu processing), and saas. I als want to make video editor plugin integrations so you don’t have to leave your video editor. There were a lot of tradeoffs with scalability and simplicity and I’m still debating on other approaches.

Overall, thank you Cole and Dynamous and AWS for hosting this, I’ve learned so much! I am quite impressed with Kiro’s planning capabilities and task execution.

Lastly, you all have built some amazing things! I am humbled to be amongst yall, let’s continue this journey together and keep building and learning and inspiring each other!

