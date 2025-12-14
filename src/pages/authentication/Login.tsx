import { useState, ChangeEvent, FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import Button from '@mui/material/Button';
import IconButton from '@mui/material/IconButton';
import Typography from '@mui/material/Typography';
import TextField from '@mui/material/TextField';
import InputAdornment from '@mui/material/InputAdornment';
import Stack from '@mui/material/Stack';
import IconifyIcon from 'components/base/IconifyIcon';

const Login = () => {
  const navigate = useNavigate();
  const [user, setUser] = useState({ email: '', password: '' });
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');

  const handleInputChange = (e: ChangeEvent<HTMLInputElement>) => {
    setUser({ ...user, [e.target.name]: e.target.value });
    setError(''); // ล้าง Error เมื่อพิมพ์ใหม่
  };

  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    
    // >>> SIMPLE LOGIN LOGIC <<<
    // Username: admin, Password: 1234
    if (user.email === 'admin' && user.password === '1234') {
        localStorage.setItem('isAuthenticated', 'true');
        navigate('/'); // ไปหน้า Dashboard
    } else {
        setError('Incorrect username or password');
    }
  };

  return (
    <>
      <Typography align="center" variant="h3" fontWeight={600}>
        System Login
      </Typography>

      <Stack onSubmit={handleSubmit} component="form" direction="column" gap={2} mt={4}>
        
        {/* Username Field */}
        <TextField
          id="email"
          name="email"
          type="text"
          value={user.email}
          onChange={handleInputChange}
          variant="filled"
          placeholder="Username (admin)"
          autoComplete="username"
          fullWidth
          autoFocus
          required
        />

        {/* Password Field */}
        <TextField
          id="password"
          name="password"
          type={showPassword ? 'text' : 'password'}
          value={user.password}
          onChange={handleInputChange}
          variant="filled"
          placeholder="Password (1234)"
          autoComplete="current-password"
          fullWidth
          required
          InputProps={{
            endAdornment: (
              <InputAdornment position="end" sx={{ opacity: user.password ? 1 : 0 }}>
                <IconButton
                  aria-label="toggle password visibility"
                  onClick={() => setShowPassword(!showPassword)}
                  edge="end"
                >
                  <IconifyIcon icon={showPassword ? 'ion:eye' : 'ion:eye-off'} />
                </IconButton>
              </InputAdornment>
            ),
          }}
        />

        {/* Error Message */}
        {error && (
            <Typography color="error" variant="caption" align="center">
                {error}
            </Typography>
        )}

        {/* ปุ่ม Login (ขยับขึ้นมา เพราะลบ Remember/Forgot ออกแล้ว) */}
        <Button type="submit" variant="contained" size="medium" fullWidth sx={{ mt: 2 }}>
          Login
        </Button>

      </Stack>
    </>
  );
};

export default Login;