import os
import json
import pickle
import face_recognition
from dotenv import load_dotenv

load_dotenv()
static_url = os.environ.get('static_url')

class Person:
    def __init__(self, reg, name, image_name, display_name=None, pickle_name=None):
        """
        `reg:` Registration number  
        `name:` Name of person  
        `image_name:` Name of the image file (ex. 'my_name.png' only)  
        `display_name:` (Optional) Name to display (defaults to {name})  
        `pickle_name:` (Optional) Name of pickle file to create (default to {name}.pkl)  
        """
        self.RegNo = reg
        # self.name = "_".join(name.split(" "))
        self.name = name

        self.image_url = os.path.join(static_url, "pics", image_name)

        if display_name is not None:
            self.disp_name = display_name
        else:
            self.disp_name = self.name

        if pickle_name is not None:
            self.pickle_name = os.path.join(static_url, "models", pickle_name)
        else:
            self.pickle_name = os.path.join(
                static_url, "models", f"{self.name}.pkl")

    def view(self):
        def print_itm(title, detail):
            print(title.rjust(15), detail)

        print_itm("Reg No.: ", self.RegNo)
        print_itm("Name: ", self.name)
        print_itm("Disp Name: ", self.disp_name)
        print_itm("Image: ", self.image_url)
        print_itm("Pickle: ", self.pickle_name)

    def give_json(self):
        return {
            "Reg_No": self.RegNo,
            "Name": self.name,
            "Disp_name": self.disp_name,
            "Image": os.path.basename(self.image_url),
            "Pickle": os.path.basename(self.pickle_name),
        }


# bs = Person("Bhushan Songire", "Bhushan", "bhushan.jpg", "bs.pkl")

people = [
    # Person(reg, name, image_name(just image.jpg), 
    #           (optional)display_name, (optional)pickle_name),
    Person("22BCE1539", "Bhushan Songire", "bhushan.jpg", "Bhushan", "bs.pkl"),
    Person("22BCE1580", "Bhavyata Kaur", "bhavyata.jpg", "Bhavyata", "bk.pkl"),
    Person("22BCE1582", "Abhijeet Soni", "abhijeet.jpg", "as.pkl"),
    Person("22BCE1111", "Vedansh Kumar", "vedansh.jpg", "vk.pkl"),
]


class_register = []
for p in people:
    p.view()

    try:
        open_img = face_recognition.load_image_file(p.image_url)
    except Exception as e:
        print("\t\t[#] Image not found, try again...", e)

    try:
        print("\t\t[#] Modelling the image...")
        face_encoding = face_recognition.face_encodings(open_img)[0]

        os.makedirs(os.path.dirname(p.pickle_name), exist_ok=True)
        with open(p.pickle_name, "wb") as f:
            pickle.dump(face_encoding, f)
            print("\t\t[#] Saved the model...")

    except Exception as e:
        print("\t\t[#] Some error occurred!", e)

    class_register.append(p.give_json())
    print()


# student register
# Define the path for the JSON file
class_file = os.path.join(static_url, os.environ.get('class_register'))
with open(class_file, "w") as file:
    json.dump(class_register, file, indent=4)
print(F"Saved file: `{class_file}`")

print()
print("All Done!!!")
