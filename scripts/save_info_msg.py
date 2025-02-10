#!/usr/bin/env python3

import rospkg
import os, sys
from gtts import gTTS
from playsound import playsound


class TextRecorder:
    def __init__(self, root_dir, playback=False):
        self.root_dir = root_dir
        self.playback = playback
        self.tts = None
        self.sound_file_name = 'test.mp3'
        self.sound_file_dir = self.root_dir + '/config/sound_files/'
        self.sound_file_text_dir = self.root_dir + '/config/sound_file_text/'
        
    def text2mp3(self, file_name: str, text: str, lang='ko'):
        if file_name.endswith('.mp3'):
            tmp_file_name = file_name
        else:
            print('[WARNING] Invalid file name. File name is set to \'test.mp3\'.')
        
        if len(text) == 0:
            print('[ERROR] No text found.')
            return
        else:
            try:                
                tts = gTTS(text=text, lang=lang)
                if not os.path.isdir(self.root_dir + '/config/'):
                    os.mkdir(self.root_dir + '/config/')
                    print('[INFO] Save directory created.')
                    os.mkdir(self.sound_file_dir)
                    print('[INFO] Sound files: {}'.format(self.sound_file_dir))
                    os.mkdir(self.sound_file_text_dir)
                    print('[INFO] Text  files: {}'.format(self.sound_file_text_dir))
                    
                tts.save(self.sound_file_dir + tmp_file_name)
                with open(self.sound_file_text_dir + tmp_file_name[:-4] + '.txt', 'w') as f:
                    f.write(text)
                    
                print('[INFO] Text converted to sound file.')
                print('[INFO] Sound file dir: {}'.format(self.sound_file_dir + tmp_file_name))
                print('[INFO] Text  file dir: {}'.format(self.sound_file_text_dir + tmp_file_name))
                
                if self.playback:
                    playsound(self.sound_file_dir + tmp_file_name)
                
            except Exception as e:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                print('[ERROR] {}, {}, {}'.format(exc_type, fname, exc_tb.tb_lineno))
                print('[ERROR] : {}'.format(e))
                return -1
            

if __name__ == '__main__':
    rp = rospkg.RosPack()
    root_dir = rp.get_path('ltrp_broadcast_ros')
    playback = False
    
    TTS = TextRecorder(root_dir=root_dir,
                       playback=playback)
    
    ###########   EDIT HERE   ################
    text_to_save = '''GOOGLE TTS TO MP3 PYTHON TEST SCRIPT'''
    file_name_to_save = 'test.mp3'            
    lang='ko'
    ##########################################
    
    TTS.text2mp3(
        file_name=file_name_to_save,
        text=text_to_save,
        lang=lang
    )