import requests
import os
import time

a_list = [
    """Coffee and Creativity: 'Many great thinkers and artists swear by coffee's ability to boost creativity. Beethoven was such a fan that he counted out 60 beans per cup!'""",
    """Decaf Coffee Facts: 'Decaffeination doesn't mean 100% caffeine-free. Decaf coffee still contains minimal amounts of caffeine, but much less than regular coffee.'""",
    """The Impact of Coffee on Global Economy: 'Coffee is the second most traded commodity in the world, after oil. It plays a significant role in the economies of many developing countries.'""",
    """Sustainable Coffee Practices: 'Sustainable coffee growing focuses on environmentally friendly practices and fair compensation for farmers. It's all about enjoying coffee while caring for the planet and its people.'""",
    """Imagine this: the world's first coffee houses appeared in Istanbul in the 16th century. Back then, coffee houses were not just places to enjoy coffee but also centers for people to gather and discuss politics and culture.""",
    """Did you know that some people prefer adding salt to their coffee instead of sugar? This is a tradition in some cultures to balance the bitterness of the coffee.""",
    """Interestingly, although coffee originated in Africa, Brazil is now the largest producer of coffee in the world. Coffee truly is a beverage that has traveled around the globe!""",
    """In some countries, like Italy, it's customary to add sugar to an espresso. In other places, this might be seen as disrespecting the natural flavor of the coffee.""",
    """Coffee holds different meanings in various cultures. In Arab culture, offering coffee is a traditional way to welcome guests.""",
    """Scientists have found that just the aroma of coffee can be stimulating. So sometimes, just smelling coffee is enough to make one feel more alert.""",
    """The amount of coffee beans consumed worldwide each year is enough to circle the Earth's equator more than 10 times! Isn't that an incredible statistic?""",
    """Beethoven was a great lover of coffee and was very particular about his brew, insisting on exactly 60 beans per cup. This attention to detail is also reflected in his music.""",
    """Did you know that coffee was originally consumed as a food, not a beverage? The first coffee consumers actually ate coffee beans mixed with animal fat.""",
    """Coffee is more than just a drink; it's a culture. People meet in coffee shops, share stories, and make history. Every cup of coffee carries its own story.""",
    """Let's talk about the evolution of the coffee drink. Did you know that the way we enjoy coffee today has changed drastically over the centuries? Originally, coffee beans were consumed in Africa as energy balls mixed with fat, and it wasn't until the 15th century that they began to be brewed into a drink in Yemen.""",
    """Have you ever wondered about the journey of a coffee bean? From the lush coffee farms, often located in beautiful, mountainous regions, to the intricate process of harvesting, drying, and roasting, each step profoundly influences the final taste of your coffee. It's a global journey from the farm to your cup.""",
    """The science behind brewing the perfect cup of coffee is quite complex. Factors like water temperature, grind size, brewing time, and even the water's mineral content play a significant role in extracting the ideal flavor from coffee beans. Each variable can completely change your coffee experience.""",
    """In different cultures, coffee plays various roles. For instance, in Ethiopia, the birthplace of coffee, the coffee ceremony is an integral part of social and cultural life. It involves roasting beans, brewing in a clay pot called a 'jebena', and sharing with family and friends.""",
    """The world of specialty coffee is fascinating. It's similar to wine in terms of the diversity of flavors, which are influenced by the coffee's origin, varietal, altitude, and processing method. Tasting coffee from different regions is like a sensory trip around the world.""",
    """Did you know that espresso doesn't refer to a specific type of bean but rather to the method of brewing? 'Espresso' means 'expressed' or 'pressed out' in Italian, referring to the way the coffee is made by forcing hot water through finely-ground coffee.""",
    """The impact of coffee on art and culture cannot be understated. From the vibrant café cultures of Paris and Vienna to the modern coffee shop scenes around the world, coffee has always been a catalyst for social interaction, intellectual discussion, and artistic expression.""",
    """Sustainability in coffee production is becoming increasingly important. As a coffee enthusiast, you can contribute to this by choosing coffee that is ethically sourced and supports fair trade practices. This not only helps improve the lives of coffee farmers but also ensures the longevity and health of coffee production worldwide.""",
    """Finally, let's talk about the future of coffee. With advancements in technology and a growing emphasis on sustainability and quality, the way we grow, brew, and enjoy coffee is continually evolving. The future of coffee looks as exciting as its past.""",
    """While discussing coffee, one can't overlook its close connection with music. Many coffee shops carefully select music to create a unique coffee experience atmosphere. Sometimes, music can even alter our perception of the taste of coffee.""",
    """The environmental impact of coffee is an important topic. Sustainable cultivation and sourcing matter not only for the quality of coffee but also for the responsibility towards our planet and the future. Choosing certified organic and fair-trade coffee can help protect our environment.""",
    """You might have heard of cold brew coffee, but do you know how it differs from hot coffee? Cold brew is steeped in cold water over a long period, reducing acidity and bitterness for a smoother coffee.""",
    """Each region of the world offers coffee with unique flavors. For instance, African coffees often have distinct fruity and floral notes, while Latin American coffees tend to have nutty and chocolatey flavors.""",
    """Coffee has also played significant roles in history. During the American Revolution and the French Revolution, coffee houses became hotbeds of political activity.""",
    """Many baristas showcase their artistic talents through coffee latte art. Each carefully crafted cup of coffee is a work of art, reflecting the skill and creativity of its maker.""",
    """Storing coffee is also a science. Properly storing coffee beans can maintain their freshness and flavor. It's generally recommended to keep coffee beans in a dry, cool place, away from light.""",
    """With increasing health consciousness, decaf and low-caffeine coffees are becoming more popular. These coffees offer the traditional flavor of coffee but reduce caffeine intake.""",
    """The future of coffee is filled with endless possibilities. From new types of coffee machines to innovations in sustainable cultivation, the coffee industry is continuously evolving and changing, bringing us more diverse coffee experiences.""",
    ]

coffee_knowledge_transition = "Let’s hear a little story about coffee"

dance_transition = "Coffee's almost ready; let's sway to the rhythm until it's done."

mood_transition = [
    """How are you feeling today? Did you know there are many simple ways to help regulate our mood and make the day more enjoyable? For example:""",
    """Hello there! How's your day going? It’s always good to check in with ourselves about our mood. Here are some interesting ideas and tips to help keep your spirits up:"""]

mood = [
    """Mindfulness Meditation: 'Spending a few minutes each day on mindfulness meditation can greatly improve your mood and focus. Simple breathing exercises can help you relax and concentrate.'""",
    """Nature's Healing: 'Spending time in nature can significantly uplift your mood. Even a short walk can help you relax and rejuvenate.'""",
    """The Power of Music: 'Listening to music is a great way to boost your mood. Different types of music can help change our emotions.'""",
    """Healthy Eating: 'A balanced diet can have a big impact on your mood. A proper diet is not only good for the body but also makes the heart happier.'""",
    """Gratitude Practice: 'Taking time each day to appreciate the little things in life is a simple and effective way to improve your mood.'""",
    """Positive Self-Talk: 'Speaking positively to yourself, encouraging yourself, has a very good effect on your mindset.'""",
    """Creative Activities: 'Engaging in creative activities, such as painting or writing, can relax your mind and reduce stress.'""",
    """Social Interaction: 'Communicating with others is an effective way to lift your mood. Chat with friends and family, share some happy things.'""",
    """Regular Exercise: 'Exercise not only improves physical health but can also make your mood better.'""",
    """Adequate Sleep: 'Ensuring enough sleep is very important for maintaining a good mood.'""",
    """The World of Books: 'Diving into a good book can be a wonderful escape and mood lifter. Whether it’s fiction, non-fiction, or poetry, reading opens up new worlds and perspectives. What’s your favorite book that you’d recommend?'""",
    """Gardening Joys: 'Did you know that gardening, even if it's just tending to a few plants, can be incredibly therapeutic? It connects us with nature and can be a soothing, grounding experience.'""",
    """Artistic Expression: 'Expressing yourself through art can be a great way to deal with emotions. Painting, sculpting, or even doodling can help channel your feelings in a positive direction.'""",
    """Cooking and Baking: 'Cooking or baking can be more than just preparing food; it can be an act of self-care. The process of creating something delicious can be really satisfying and uplifting.'""",
    """Learning Something New: 'Have you thought about learning a new skill or hobby? It could be a new language, a musical instrument, or even a new coffee brewing technique. Learning keeps the mind engaged and brings a sense of accomplishment.'""",
    """Mindfulness and Yoga: 'Practicing mindfulness or yoga can be very beneficial for mental health. These activities help in reducing stress and improving overall mood by focusing on the present moment.'""",
    """Pet Therapy: 'Spending time with pets can be incredibly uplifting. Their unconditional love and presence can have a calming effect.'""",
    """Volunteering: 'Helping others can also boost your own mood. Volunteering for a cause you care about can bring a sense of fulfillment and connection.'""",
    """Exploring Nature: 'Take the time to explore the outdoors. Hiking, biking, or simply walking in a park can refresh your mind and body.'""",
    """Aromatherapy: 'The power of scent can be quite remarkable. Certain aromas, like lavender or peppermint, can have a relaxing or invigorating effect.'""",
    """Journaling: 'Writing down your thoughts and feelings can be a great way to process emotions and reflect on your day. It’s a private space to express yourself freely.'""",
    """Laugh and Smile: 'Never underestimate the power of laughter and smiling. Watching a funny movie or sharing jokes with friends can lift your spirits.'""",
    """Travel Tales: 'Traveling can open our minds and hearts. Have you ever experienced a moment during your travels that completely changed your perspective? Sometimes, even virtual travel through documentaries or travel blogs can be eye-opening.'""",
    """Fitness Fun: 'Did you know that even light exercise, like a brisk walk or a short dance session, can significantly boost your mood? It's all about finding a fun way to move and enjoy the process.'""",
    """Creative Cooking: 'Experimenting with new recipes can be a delightful adventure. It’s not just about the taste, it’s about the creativity in mixing and matching ingredients. What’s the most unusual dish you’ve ever cooked?'""",
    """Mind-Challenging Games: 'Engaging in brain games or puzzles can be a great way to keep your mind sharp. It’s not only fun but also helps in enhancing cognitive skills. Do you have a favorite brain game?'""",
    """DIY Projects: 'DIY projects can be incredibly rewarding. There’s something special about creating something with your own hands, whether it’s a piece of art, a home repair, or a craft project.'""",
    """Cultural Exploration: 'Exploring different cultures, whether through food, music, art, or language, can be a fascinating journey. It allows us to understand and appreciate the diversity of the world around us.'""",
    """Humor and Comedy: 'Laughter is often called the best medicine. Watching a comedy show or listening to a funny podcast can be a quick mood enhancer. What’s your favorite source of laughter?'""",
    """Photography as a Hobby: 'Photography can be a wonderful way to capture and appreciate the beauty around us. It encourages us to look at our environment with new eyes. Do you enjoy photography?'""",
    """Relaxation Techniques: 'Practicing relaxation techniques like deep breathing, meditation, or gentle stretching can have a calming effect on the mind and body. It's important to take a few moments of tranquility in our busy lives.'""",
    """Music Exploration: 'Exploring new genres of music or rediscovering old favorites can be a delightful way to enhance your day. Music has the power to evoke memories, emotions, and even inspire new ideas.'""",
    """Positive Affirmations: 'Starting the day with positive affirmations can set a hopeful tone for the rest of the day. It’s about cultivating a positive mindset and focusing on your strengths.'""",
    """Nature and Wildlife: 'Observing nature and wildlife can be a grounding experience. It reminds us of the beauty and complexity of the natural world. Do you have a favorite place to enjoy nature?'"""]

coffee_introduction_transition = "Let me tell you the story about this coffee"

# Iced Latte \ Americano \ Latte \ Foamy Hazelnut Latte
coffee_introduction = [
    """A cool escape, this drink combines fresh espresso with icy milk for a creamy, refreshing pick-me-up. Perfect for a serene break any time.""",
    """Americano coffee, originating from WWII American soldiers, is a simple yet flavorful blend of espresso and water, reflecting a piece of history and cultural fusion. Ideal for a refreshing morning or a relaxing afternoon pause, it offers a timeless coffee experience.""",
    """Latte is espresso's milder counterpart, softened by steamy milk for a soothing effect. It's creamy, comforting, and perfect for easygoing mornings or relaxed afternoons.""",
    """Foamy Hazelnut Latte is a masterpiece of espresso, ice, and milk, whipped with hazelnut and condensed milk into a creamy, frothy delight. It's the ultimate treat for those who love a sweet, cool latte."""
]

# Espresso \ Cappuccino \ Double Espresso \ Chocolate Cold Brew \ Iced Americano \ Iced Foam Latte
# \ Coconut Latte \ Rose Orange Cold Brew \ Vanilla Cold Brew \ Whiskey Cold Brew
add_coffee_introduction = [
    """Espresso is a vibrant, compact burst of coffee, turning lackluster mornings into go-getter days. It's strong, snappy, and gets you going,remember to savor each sip.""",
    """Cappuccino, an Italian specialty, presents a harmonious trio of espresso, steamed milk, and milk foam, delivering a rich, layered coffee experience. Savored typically at breakfast, it provides a smooth, foamy start to any day with its deep, aromatic flavors.""",
    """Doppio, or Double Espresso, doubles down on flavor and energy. It's a rich, powerful shot for those who want an extra boost. Ideal for coffee lovers looking for twice the buzz.""",
    """Chocolate Cold Brew combines cold brew and ice for a refreshing start, topped with a rich chocolate milk foam for a luxurious twist. It's a sweet, chilled journey in every sip,perfect for sunny days or when you need a sweet fix.""",
    """Iced Americano offers a cool burst of espresso over ice, striking the right balance between strong coffee and refreshing chill. Ideal for a refreshing pick-me-up on warm days.""",
    """A refreshing blend of iced milk and rich, frothy espresso. Sweet, condensed milk layers with icy smoothness for a quick, delightful coffee fix.""",
    """A tropical take on the classic latte with creamy coconut milk and a hint of espresso sweetness. Garnish to your liking for an exotic coffee retreat.""",
    """An aromatic cold brew with a citrusy rose twist, creating a unique, floral-infused coffee experience. Ideal for those who love to try new, sophisticated flavors.""",
    """Smooth cold brew with a vanilla infusion offers a subtly sweet, comforting coffee experience. It's a luxurious twist on a classic favorite.""",
    """A bold combination of cold brew coffee and whiskey for a deep, smoky taste. It's an adventurous drink for an evening wind-down or a distinguished coffee break.""",
]

# Iced Latte \  Americano \  Latte  \ Foamy Hazelnut Latte

# num = 34
# i = num-1
# print(f"i:{i}")
# print(f"num:{num}")
params = {'text': add_coffee_introduction[9], 'sync': False}
url = "http://192.168.2.191:9004/audio/gtts"

res = requests.post(url, params=params, timeout=3)
# logger.info('url={} params={}, result={}'.format(url, params, res.content))


time.sleep(3)

# 获取当前工作目录中的文件列表
files = os.listdir('.')  # 这里的'.'代表当前目录，你可以根据需要修改路径

# 输出当前目录下的文件列表
# print("当前目录下的文件：", files)

# for i in files:
# i=1

if os.path.exists('gtts_out.mp3'):
    print("exist")
    for i in files:
        if i == 'gtts_out.mp3':
            os.rename('gtts_out.mp3', f'coffee_introduction_Whiskey Cold Brew.mp3')
else:
    print("not exist")
