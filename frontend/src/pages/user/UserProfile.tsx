import React, { useEffect, useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../utils/apiClient';
import UserLayout from '../../components/layout/UserLayout';

export default function UserProfile() {
  const { user, logout } = useAuth();
  const [profile, setProfile] = useState<any>(null);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({ name: '', company: '', industry: '' });
  const [msg, setMsg] = useState('');

  useEffect(() => {
    api.get<any>('/profile/').then(d => {
      setProfile(d);
      setForm({ name: d.name, company: d.company || '', industry: d.industry || '' });
    }).catch(() => {});
  }, []);

  const save = async () => {
    await api.put('/profile/', form);
    setMsg('Profile updated successfully.');
    setEditing(false);
    api.get<any>('/profile/').then(setProfile);
    setTimeout(() => setMsg(''), 3000);
  };

  const industries = ['Logistics', 'Healthcare', 'Retail', 'Education', 'Manufacturing', 'Finance', 'Hospitality', 'Technology', 'Other'];

  return (
    <UserLayout>
      <div className="p-6 space-y-6 max-w-2xl">
        <h1 className="text-2xl font-bold text-slate-900">My Profile</h1>
        {msg && <div className="bg-green-50 border border-green-200 text-green-700 rounded-lg px-4 py-2 text-sm">{msg}</div>}

        {/* Profile Header */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
          <div className="flex items-center gap-4">
            <div className="w-16 h-16 rounded-full bg-blue-600 text-white flex items-center justify-center text-xl font-bold">
              {user?.avatar_initials || 'U'}
            </div>
            <div className="flex-1">
              <h2 className="text-lg font-bold text-slate-900">{profile?.name ?? user?.name}</h2>
              <p className="text-sm text-slate-500">{profile?.email ?? user?.email}</p>
              <p className="text-sm text-slate-500">{profile?.company}</p>
              <div className="flex gap-2 mt-1">
                <span className="px-2 py-0.5 rounded-full text-xs bg-blue-50 text-blue-700 font-medium">
                  {profile?.subscription?.plan_name ?? 'No plan'}
                </span>
                <span className="text-xs text-slate-400">
                  Member since {profile?.created_at ? new Date(profile.created_at).toLocaleDateString() : '—'}
                </span>
              </div>
            </div>
            <button onClick={() => setEditing(!editing)}
              className="px-4 py-2 rounded-lg text-sm bg-slate-100 text-slate-600 hover:bg-slate-200">
              {editing ? 'Cancel' : 'Edit Profile'}
            </button>
          </div>
        </div>

        {/* Edit Form */}
        {editing && (
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-4">
            <h3 className="font-semibold text-slate-900">Edit Profile</h3>
            <div>
              <label className="text-sm text-slate-600">Name</label>
              <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })}
                className="w-full mt-1 px-3 py-2 rounded-lg border border-slate-300 text-sm" />
            </div>
            <div>
              <label className="text-sm text-slate-600">Company</label>
              <input value={form.company} onChange={e => setForm({ ...form, company: e.target.value })}
                className="w-full mt-1 px-3 py-2 rounded-lg border border-slate-300 text-sm" />
            </div>
            <div>
              <label className="text-sm text-slate-600">Industry</label>
              <select value={form.industry} onChange={e => setForm({ ...form, industry: e.target.value })}
                className="w-full mt-1 px-3 py-2 rounded-lg border border-slate-300 text-sm">
                <option value="">Select...</option>
                {industries.map(i => <option key={i} value={i}>{i}</option>)}
              </select>
            </div>
            <div className="bg-slate-50 rounded-lg p-3 space-y-1 text-sm">
              <p className="text-slate-500">Email: <span className="text-slate-700">{profile?.email}</span> (read-only)</p>
              <p className="text-slate-500">Role: <span className="text-slate-700">{profile?.role}</span></p>
              <p className="text-slate-500">Account ID: <span className="font-mono text-slate-700">{profile?.id}</span></p>
            </div>
            <button onClick={save} className="px-6 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700">
              Save Changes
            </button>
          </div>
        )}

        {/* Account Stats */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
          <h3 className="font-semibold text-slate-900 mb-3">Account Stats</h3>
          <div className="grid grid-cols-3 gap-4">
            <div className="text-center">
              <p className="text-2xl font-bold text-slate-900">{profile?.sites?.length ?? 0}</p>
              <p className="text-xs text-slate-500">Sites Registered</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-slate-900">{profile?.role === 'BUSINESS_OWNER' ? 'Active' : profile?.role}</p>
              <p className="text-xs text-slate-500">Account Status</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-slate-900">{profile?.subscription?.plan_name ?? '—'}</p>
              <p className="text-xs text-slate-500">Current Plan</p>
            </div>
          </div>
        </div>

        {/* Sign Out */}
        <div className="bg-white rounded-xl border border-red-200 shadow-sm p-6">
          <h3 className="font-semibold text-red-700 mb-2">Sign Out</h3>
          <p className="text-sm text-slate-500 mb-3">End your current session and return to the login page.</p>
          <button onClick={logout} className="px-4 py-2 rounded-lg bg-red-50 text-red-600 text-sm font-medium hover:bg-red-100">
            Sign Out
          </button>
        </div>
      </div>
    </UserLayout>
  );
}
