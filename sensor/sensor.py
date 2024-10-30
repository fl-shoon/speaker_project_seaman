import logging 

logging.basicConfig(level=logging.INFO)
sensor_logger = logging.getLogger(__name__)

class SpeakerSensor:
    def __init__(self, serial_module, fire_client):
        self.serial_module = serial_module
        self.fire_client = fire_client
        self.auth_token =  None
        self.last_sensor_data = None

    def update_sensor_data(self):
        current_sensor_data = self.get_current_sensor_data()
        if self.should_update_sensor_data(current_sensor_data):
            try:
                success = self.fire_client.update_sensor_data(current_sensor_data)
                if success:
                    self.last_sensor_data = current_sensor_data
                else:
                    sensor_logger.error("Failed to update sensor data")
            except Exception as e:
                sensor_logger.error(f"Error updating sensor data: {e}")

    def should_update_sensor_data(self, current_sensor_data):
        if not self.last_sensor_data:
            return True
        
        thresholds = {
            'temperatureSensor': 0.5,  
            'irSensor': None,  
            'brightnessSensor': 5.0  
        }
        
        for key, threshold in thresholds.items():
            if key not in self.last_sensor_data:
                return True
            
            current_value = current_sensor_data.get(key)
            last_value = self.last_sensor_data.get(key)
            
            if current_value is None or last_value is None:
                return True
            
            if isinstance(current_value, bool):
                if current_value != last_value:
                    return True
            else:
                try:
                    if abs(float(current_value) - float(last_value)) >= threshold:
                        return True
                except ValueError:
                    if current_value != last_value:
                        return True
        
        return False

    def get_current_sensor_data(self):
        inputs = self.serial_module.get_inputs()
        if inputs and 'result' in inputs:
            result = inputs['result']
            
            '''
                # example of sensor results
                Thermal: 30.24°C
                IR Detect: True
                Luminosity: 20.00 lux
            '''
            
            return {
                'temperatureSensor': f"{result['thermal']:.2f}",
                'irSensor': result['ir_detect'],
                'brightnessSensor': f"{result['luminosity']:.2f}"
            }
        return {}