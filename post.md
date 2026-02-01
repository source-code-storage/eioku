Codi Huston

Hackathon Participan...
17h

Learn. Innovate. Obsess. Then do it again!
Hi there, thanks for reaching out! Here’s a brief set of examples! Thanks!

### Example 1
```
Audience: content creator who produces video essays
Problem: I have 100 GBs / 80+ hours of of video from recording a video game that I cover lore for
Solution: Eioku allows me to find the exact moments I’ve storyboarded for my YouTube video (via on screen text, audio transcripts) vs me opening each video independently to find the relevant moments 
```

### Example 2
```
Audience: I am a content creator / corporation / enterprise / business with a trove of content over the years
Problem: what topics have I covered (or not) or mentioned, and what degree of quality did I deliver it in? I can use this to prepare future material / marketing / training material (video or otherwise)
Solution: Eioku in its current form allows you to find exactly when you’ve spoken about. In the future, semantic search makes querying more natural, an LLM integration can review your transcript and opine on improvements to delivery style or script, etc. (transcript), and trends/topics can be surfaced
```

### Example 3
```
Audience: Film editors that get hundreds of GBs of footage from the field production team (sometimes daily!) with tight deadlines on delivery
Problem: I need to find A/B-roll of my travels for my next vlog. Perhaps this video references multiple places, at various periods of time, and I’m comparing experiences (boat rides, hiking excursions, city life)
Solution: Eioku lets you search videos by location, objects, and in the future: recognized faces
```

### Example 4
```
Audience: Family and friends who record memorable moments
Problem: Remember that one time when person X did that thing Y? Can we compile a video focused on person Z over the past year?
Solution: Eioku’s features let you quickly find and relive those moments, and makes compiling them for that special sentimental video much less daunting of a task
```

---
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

