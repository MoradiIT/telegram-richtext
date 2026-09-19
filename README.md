# Telegram Richtext Composer
This Python application helps you create and edit rich-text content for your Telegram channel.

I created this application as a comprehensive editor for Telegram bot messages, with support for the Markdown and HTML formatting options accepted by the Telegram Bot API. The goal is to make it easier to create, edit, and publish richly formatted Telegram messages without manually writing formatting tags.

Because the available tools do not support all of Telegram's available formatting options, I decided to create my own editor to provide a more complete solution. I am a long-time Telegram user and a big fan of its features, and I wanted an editor that would make it easier to take advantage of Telegram's rich-text capabilities.

## Requirements

Before using the application, you need:

* A public Telegram channel with a unique username/ID.
* A Telegram bot and its bot token.
* A Windows PC with Python installed.

## How to Use

Follow these steps to send rich-text messages to your Telegram channel:

1. Add your bot to the Telegram channel.
2. Make sure the bot has permission to **Send Messages**.
3. Open the Python script in a text editor.
4. Add your bot token and public channel username/ID to the corresponding lines:

```python
BOT_TOKEN = "****"
CHANNEL = "@****"
```

5. Save the script.
6. Run the script. You can usually launch it by double-clicking the `.py` file if Python is properly associated with Python files on your PC.
7. Create your message using the editor and click **Publish** to send it to your channel.

## Notes

* If Telegram is restricted or blocked on your network or in your region, you may need to use a VPN or another permitted network connection so the application can connect to the Telegram Bot API.
* The preview pane may not always render every formatting option exactly as Telegram does. The formatting syntax has been tested, and the published message should be rendered correctly in Telegram.
* At the time of publishing this project, some rich-text messages may appear differently between Telegram's mobile and desktop applications. This is controlled by Telegram and is not caused by this application.
* Persian text in titles may appear as regular text in the preview pane. The formatting is preserved and will be displayed correctly after the message is published to Telegram.
* When publishing a message containing a large file, the application may take some time to complete the upload. The required time depends on the file size and your Internet connection speed.
* Python must be installed on your PC to run the application.
* To launch the application, simply double-click the Python script, provided that `.py` files are associated with Python on your system.
* To insert an empty line between two paragraphs of regular text, use the **Empty Line** button.
* To add spacing before a title or after formatted text, insert `<br>` where required.

## Screenshot

The screenshot below shows the application's interface:

