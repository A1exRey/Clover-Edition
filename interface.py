from getconfig import settings, colors, setting_info
from utils import pad_text


def boolValue(bool):
    return "on" if bool else "off"


def instructions():
    print('\n' +
          'AID2: Инструкции \n' +
          '  Описывай действия с глагола т.е. "идешь в таверну", "взмахнул мечом""\n' +
          '  Для описания диалога используй конструкцию ">ты говоришь что-то" или "" для прямой речи"\n' +
		  '  Чтобы вставить свою историю в текст введи !(сюжетный_текст)\n'+
          '  Если кажется, что модель не договорила и оборвалась на полуслове то отправь пустой текст (просто enter нажми) и модель допишет текст')
    print('The following commands can be entered for any action:')
    print('  "/revert"                Reverts the last action allowing you to pick a different action.')
    print('  "/quit"                  Quits the game and saves')
    print('  "/menu"                  Starts a new game and saves your current one')
    print('  "/retry"                 Retries the last action')
    print('  "/restart"               Restarts the current story')
    print('  "/print"                 Prints a transcript of your adventure (without extra newline formatting)')
    print('  "/alter"                 Edit the last prompt from the AI')
    print('  "/altergen"              Edit the last result from the AI and have it generate the rest')
    print('  "/context"               Edit the story\'s permanent context paragraph')
    print('  "/remember [SENTENCE]"   Commits something permanently to the AI\'s memory')
    print('  "/forget"                Opens a menu allowing you to remove permanent memories')
    print('  "/save"                  Saves your game to a file in the game\'s save directory')
    print('  "/load"                  Loads a game from a file in the game\'s save directory')
    print('  "/summarize"             Create a new story using by summarizing your previous one')
    print('  "/help"                  Prints these instructions again')
    print('  "/set [SETTING] [VALUE]" Sets the specified setting to the specified value.:')
    for k, v in setting_info.items():
        print(pad_text('        ' + k, 27) + v[0] + (" " if v[0] else "") +
              "Default: " + str(v[1]) + " | "
              "Current: " + settings.get(k))
